-- =====================================================================
-- 020 — Hardening de seguranca (fecha os alertas do Supabase Advisor, Ago/2026)
-- =====================================================================
-- Principio: o APP (dashboard + IAlex) usa a chave SERVICE_ROLE, que IGNORA RLS
-- (atributo BYPASSRLS). Logo, LIGAR RLS e REMOVER as policies "abertas" NAO quebra
-- o app — apenas fecha o acesso pela chave ANON (publica).
--
-- Unica excecao publica (chave anon): o Worker do Cloudflare em
-- dados.iaprendo.com.br, que (a) procura companies pelo inep e (b) grava
-- opr_pageviews (tracking do OPR). As duas excecoes ficam explicitas e MINIMAS.
--
-- Como aplicar: Supabase Dashboard -> SQL Editor -> New query -> colar tudo -> Run.
-- Reversivel (ver bloco ROLLBACK comentado no fim).
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- 1) ERROR "RLS Disabled in Public": ligar RLS em 6 tabelas sem protecao.
--    Sem policy p/ anon => anon BLOQUEADO; service_role continua (bypassa).
--    Nenhuma e usada pelo Worker anon => seguro fechar 100%.
-- ---------------------------------------------------------------------
alter table public.learned_skills        enable row level security;
alter table public.school_analytics      enable row level security;
alter table public.rede_overrides        enable row level security;
alter table public.school_enem_yearly    enable row level security;
alter table public.school_censo_yearly   enable row level security;
alter table public.urgency_score_history enable row level security;

-- ---------------------------------------------------------------------
-- 2) WARN "RLS Policy Always True": as policies "Allow all for service role"
--    estavam com USING(true) p/ TODOS os papeis (inclusive ANON) => dados
--    efetivamente abertos (incl. contacts = PII!). Como service_role IGNORA
--    RLS, o app nao precisa delas: basta remover (fecha anon; app segue).
-- ---------------------------------------------------------------------
drop policy if exists "Allow all for service role" on public.contacts;
drop policy if exists "Allow all for service role" on public.approval_queue;
drop policy if exists "Allow all for service role" on public.interactions;
drop policy if exists "Allow all for service role" on public.meetings;
drop policy if exists "Allow all for service role" on public.campaigns;
drop policy if exists "Allow all for service role" on public.api_usage;
drop policy if exists "Allow all for service role" on public.companies;

-- Garante RLS ligado nessas 7 (idempotente):
alter table public.contacts       enable row level security;
alter table public.approval_queue enable row level security;
alter table public.interactions   enable row level security;
alter table public.meetings       enable row level security;
alter table public.campaigns      enable row level security;
alter table public.api_usage      enable row level security;
alter table public.companies      enable row level security;

-- EXCECAO 1 (Worker OPR): anon so precisa ACHAR o id da escola pelo inep.
-- Limita as COLUNAS visiveis a anon ao minimo (nada de score/telefone/etc.)
-- e permite so SELECT (nunca escrita).
revoke select on public.companies from anon;
grant  select (id, inep_code) on public.companies to anon;
drop policy if exists "anon lookup companies by inep (worker OPR)" on public.companies;
create policy "anon lookup companies by inep (worker OPR)"
  on public.companies for select to anon using (true);

-- EXCECAO 2 (Worker OPR): anon grava tracking em opr_pageviews (intencional).
-- Mantem a policy de INSERT que ja existe; so garante RLS ligado:
alter table public.opr_pageviews enable row level security;

-- ---------------------------------------------------------------------
-- 3) ERROR "Security Definer View": passar as 3 views p/ security_invoker,
--    assim respeitam o RLS de quem consulta (o app = service_role segue vendo).
-- ---------------------------------------------------------------------
alter view public.opr_pageviews_summary set (security_invoker = on);
alter view public.leads_qualified       set (security_invoker = on);
alter view public.api_usage_monthly     set (security_invoker = on);

-- ---------------------------------------------------------------------
-- 4) WARN "Function Search Path Mutable": fixar search_path (hardening).
-- ---------------------------------------------------------------------
alter function public.update_updated_at_column() set search_path = public, pg_temp;
alter function public.log_stage_change()         set search_path = public, pg_temp;
alter function public.mec_catalog_cities(text[]) set search_path = public, pg_temp;
alter function public.mec_catalog_facets()       set search_path = public, pg_temp;

commit;

-- =====================================================================
-- ROLLBACK (se algo do Worker parar) — reabre companies p/ anon:
--   grant select on public.companies to anon;
--   -- e, se necessario, recriar a policy ampla numa tabela especifica:
--   -- create policy "tmp open" on public.<tabela> for all using (true);
-- Mas o esperado e ZERO impacto no app (service_role) e no Worker (excecoes acima).
-- =====================================================================
