"""
PerplexityBrowser - Busca contatos de escolas via Perplexity no navegador.

Usa Playwright para automatizar o Perplexity.ai no Chrome do usuario,
aproveitando a assinatura Pro sem custo de API.

IMPORTANTE: Na primeira execucao, pode pedir login manual. Depois os cookies
ficam salvos e as proximas buscas sao automaticas.

Uso:
    from tools.perplexity_browser import perplexity_browser
    contacts = perplexity_browser.search_school_contacts("Colegio Bom Conselho", "Porto Alegre", "RS")
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from utils.logger import logger

# Pasta para salvar cookies/sessao do navegador (caminho curto para evitar problemas com espacos)
BROWSER_DATA_DIR = Path.home() / ".iaprendo-browser"


class PerplexityBrowser:
    """Busca contatos de escolas via Perplexity no navegador."""

    def __init__(self) -> None:
        self._enabled = True
        self._browser = None
        self._context = None
        self._page = None

    def is_available(self) -> bool:
        """Verifica se o Playwright esta instalado."""
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            logger.warning("Playwright nao instalado. Execute: pip install playwright && python -m playwright install chromium")
            return False

    def _ensure_browser(self) -> bool:
        """Inicia o navegador se necessario. Reutiliza sessao existente."""
        if self._page and not self._page.is_closed():
            return True
        try:
            from playwright.sync_api import sync_playwright
            BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            # Detectar Chrome do sistema
            chrome_paths = [
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            ]
            chrome_exe = None
            for p in chrome_paths:
                if Path(p).exists():
                    chrome_exe = p
                    break
            pw = sync_playwright().start()
            launch_kwargs = {
                "user_data_dir": str(BROWSER_DATA_DIR),
                "headless": False,
                "args": ["--disable-blink-features=AutomationControlled"],
                "viewport": {"width": 1280, "height": 800},
            }
            if chrome_exe:
                launch_kwargs["executable_path"] = chrome_exe
            self._browser = pw.chromium.launch_persistent_context(**launch_kwargs)
            self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
            logger.info("Navegador Playwright iniciado")
            return True
        except Exception as e:
            logger.error("Falha ao iniciar navegador", extra={"error": str(e)})
            self._enabled = False
            return False

    def _close(self) -> None:
        """Fecha o navegador."""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
                self._page = None
        except Exception:
            pass

    def search_school_contacts(
        self,
        school_name: str,
        city: str = "",
        state: str = "",
        timeout_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        """Busca contatos de uma escola no Perplexity.

        Args:
            school_name: Nome da escola.
            city: Cidade.
            state: UF.
            timeout_seconds: Tempo maximo de espera pela resposta.

        Returns:
            Lista de contatos no formato do cascade.
        """
        if not self.is_available() or not self._ensure_browser():
            return []

        prompt = self._build_prompt(school_name, city, state)
        logger.info("Perplexity: buscando contatos", extra={"school": school_name})

        try:
            page = self._page

            # Navegar para o Perplexity
            page.goto("https://www.perplexity.ai/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Verificar se precisa login
            if "sign" in page.url.lower() or "login" in page.url.lower():
                logger.warning("Perplexity: necessario login. Faca login manualmente no navegador que abriu.")
                # Esperar ate 2 minutos pelo login manual
                for _ in range(24):
                    time.sleep(5)
                    if "perplexity.ai" in page.url and "sign" not in page.url.lower():
                        break
                else:
                    logger.error("Perplexity: timeout esperando login")
                    return []

            # Encontrar campo de input (Perplexity usa div contenteditable)
            input_el = None
            for selector in ['[contenteditable="true"]', 'textarea', '[role="textbox"]']:
                if page.locator(selector).count() > 0:
                    input_el = page.locator(selector).first
                    break

            if not input_el:
                logger.error("Perplexity: campo de busca nao encontrado")
                return []

            input_el.click()
            time.sleep(0.5)
            # Limpar campo e digitar prompt
            page.keyboard.press("Control+a")
            page.keyboard.type(prompt, delay=10)
            time.sleep(1)

            # Enviar (Enter)
            page.keyboard.press("Enter")

            # Esperar resposta
            logger.info("Perplexity: aguardando resposta...")
            time.sleep(12)  # Espera inicial maior para streaming iniciar

            # Aguardar ate o conteudo parar de mudar (streaming concluido)
            last_content = ""
            stable_count = 0
            max_checks = timeout_seconds // 3
            for check_num in range(max_checks):
                time.sleep(3)
                try:
                    # Pegar texto da pagina - tentar varios seletores
                    current_content = ""
                    for sel in [".prose", ".markdown", "[class*='answer']", "[class*='response']", "article", "main"]:
                        els = page.locator(sel).all()
                        for el in els:
                            txt = el.inner_text()
                            if len(txt) > len(current_content):
                                current_content = txt

                    if not current_content:
                        # Ultimo recurso: todo o body
                        current_content = page.inner_text("body")

                    # Verificar se Perplexity ainda esta gerando (botao de stop visivel)
                    still_generating = False
                    for stop_sel in ['[aria-label="Stop"]', 'button:has-text("Stop")', '[class*="stop"]']:
                        if page.locator(stop_sel).count() > 0:
                            still_generating = True
                            break

                    if still_generating:
                        # Ainda gerando, resetar estabilidade
                        stable_count = 0
                        last_content = current_content
                        continue

                    if current_content == last_content and len(current_content) > 100:
                        stable_count += 1
                        if stable_count >= 3:
                            break  # Resposta estavel por 9 segundos
                    else:
                        stable_count = 0
                        last_content = current_content
                except Exception:
                    time.sleep(2)

            if not last_content or len(last_content) < 50:
                logger.warning("Perplexity: resposta vazia ou muito curta")
                return []

            logger.info("Perplexity: resposta recebida", extra={"chars": len(last_content)})

            # DEBUG: salvar resposta bruta para analise
            try:
                debug_path = Path(__file__).parent.parent / "logs" / "perplexity_last_response.txt"
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"=== ESCOLA: {school_name} ===\n")
                    f.write(f"=== QUERY: {self._build_prompt(school_name, '', '')} ===\n\n")
                    f.write(last_content)
                logger.info(f"Perplexity: resposta salva em {debug_path}")
            except Exception:
                pass

            # Parsear contatos da resposta
            contacts = self._parse_contacts(last_content, school_name)
            logger.info("Perplexity: contatos extraidos", extra={"count": len(contacts), "school": school_name})
            return contacts

        except Exception as e:
            logger.error("Perplexity: erro na busca", extra={"error": str(e), "school": school_name})
            return []

    # Expansao de abreviacoes comuns em nomes de escolas do MEC
    _ABBREVIATIONS = {
        "COL ": "Colegio ",
        "ESC ": "Escola ",
        "INST ": "Instituto ",
        "CTR ": "Centro ",
        "CENTR ": "Centro ",
        "FUND ": "Fundamental ",
        "ENS ": "Ensino ",
        "MED ": "Medio ",
        "PROF ": "Professor ",
        "PROFA ": "Professora ",
        "DR ": "Doutor ",
        "DRA ": "Doutora ",
        "PE ": "Padre ",
        "STO ": "Santo ",
        "STA ": "Santa ",
        "S ": "Sao ",
        "NS ": "Nossa Senhora ",
        "N S ": "Nossa Senhora ",
    }

    def _expand_school_name(self, name: str) -> str:
        """Expande abreviacoes no nome da escola para melhorar busca."""
        result = name
        # Aplicar expansoes (case insensitive)
        for abbr, full in self._ABBREVIATIONS.items():
            if result.upper().startswith(abbr):
                result = full + result[len(abbr):]
            result = re.sub(r'\b' + re.escape(abbr.strip()) + r'\b', full.strip(), result, flags=re.IGNORECASE)
        # Capitalizar adequadamente
        result = result.title()
        return result

    def _build_prompt(self, school_name: str, city: str, state: str) -> str:
        """Constroi o prompt otimizado para o Perplexity."""
        expanded = self._expand_school_name(school_name)
        location = f"{city}/{state}" if city and state else city or state or ""
        return (
            f"Liste nomes, cargos e emails da equipe de gestao do {expanded}"
            f"{' em ' + location if location else ''}: "
            f"diretor(a), vice, coordenadores pedagogicos, orientadores, "
            f"secretaria e administrativo. "
            f"Formate como tabela: Nome | Cargo | Email. "
            f"Busque emails pessoais (nome@escola) e tambem emails de setor "
            f"(secretaria@, financeiro@, etc). Inclua telefones se disponiveis."
        )

    # Palavras que indicam que a linha NAO e um nome de pessoa
    _SKIP_WORDS = {
        "nome", "name", "cargo", "nucleo", "email", "canal", "contato",
        "telefone", "endereco", "site", "fonte", "referencia", "tabela",
        "resumo", "noticias", "noticia", "colegio", "escola", "instituto",
        "coordenacao", "direcao", "apoio", "pedagogica", "pedagogico",
        "secretaria", "administrativo", "equipe", "gestao",
        "empossa", "novo", "nova", "resultado", "informacao",
    }

    def _is_valid_name(self, text: str) -> bool:
        """Verifica se o texto parece um nome de pessoa."""
        if not text or len(text) < 4:
            return False
        words = text.split()
        if len(words) < 2 or len(words) > 6:
            return False
        if any(c.isdigit() for c in text):
            return False
        # Cada palavra deve comecar com maiuscula (ou ser preposicao)
        preps = {"de", "da", "do", "dos", "das", "e"}
        for w in words:
            if w.lower() in preps:
                continue
            if not w[0].isupper():
                return False
        # Nenhuma skip word
        text_lower = text.lower()
        if any(sw in text_lower for sw in self._SKIP_WORDS):
            return False
        return True

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos para comparacao robusta."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

    def _is_valid_role(self, text: str) -> bool:
        """Verifica se o texto parece um cargo escolar."""
        if not text or len(text) < 3:
            return False
        role_keywords = [
            "diretor", "vice", "coord", "secret", "tesour", "orient",
            "pedagog", "gestor", "gerente", "supervis", "assessor",
            "professor", "educacion", "administr", "soe", "ensino",
            "psicolog", "bibliote", "nutric", "enferm", "capel",
            "pastoral", "recep", "portari", "zelador", "manuten",
            "tecnolog", "comunica", "marketing", "financ",
        ]
        text_norm = self._normalize(text)
        return any(k in text_norm for k in role_keywords)

    def _parse_contacts(self, text: str, school_name: str) -> List[Dict[str, Any]]:
        """Parseia a resposta do Perplexity para extrair contatos estruturados.

        Regras:
        - Emails pessoais sao associados ao contato por proximidade no texto
        - Emails genericos (financeiro@, contato@) NAO sao atribuidos a pessoas
          mas sim criados como contato de departamento
        - Telefones sao extraidos e associados por proximidade
        - Nunca atribuir o mesmo email a dois contatos diferentes
        """
        contacts = []
        seen_names = set()
        seen_emails = set()

        # --- Passo 1: Extrair TODOS os emails e telefones do texto ---
        all_emails = list(set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)))
        # Limpar emails: remover extensoes de imagem, emails muito curtos, pontos finais
        all_emails = [e.rstrip(".") for e in all_emails]
        all_emails = [e for e in all_emails if not e.endswith((".png", ".jpg", ".gif", ".svg")) and len(e) > 5]
        all_emails = list(set(all_emails))  # re-deduplicate apos lstrip

        phone_pattern = r'(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-.\s]?\d{4}'
        all_phones = list(set(re.findall(phone_pattern, text)))
        # Limpar telefones
        all_phones = [re.sub(r'[^\d+]', '', p) for p in all_phones]
        all_phones = [p for p in all_phones if len(p) >= 8]

        # Classificar emails: pessoais vs gerais/departamento
        general_keywords = ["contato", "secretaria", "info", "geral", "adm", "falecom",
                           "fale", "atendimento", "recepcao", "institucional", "sac",
                           "diretoria", "coordenacao", "pedagogico", "cbc", "colegio",
                           "escola", "educacao", "financeiro", "rh", "comunicacao",
                           "marketing", "matricula", "tesouraria", "biblioteca",
                           "ti", "suporte", "bolsa", "filantropia", "fundacao",
                           "curriculo", "desconto", "solidario", "pastoral",
                           "ouvidoria", "portaria", "manuten", "compras",
                           "comercial", "vendas", "eventos", "esporte"]
        general_emails = set()
        personal_emails = []
        for e in all_emails:
            prefix = e.lower().split("@")[0]
            # Email e geral se: contem keyword OU nao parece nome de pessoa
            if any(k in prefix for k in general_keywords):
                general_emails.add(e)
            elif "." in prefix or "_" in prefix:
                # Pode ser nome.sobrenome → pessoal
                personal_emails.append(e)
            elif len(prefix) <= 3:
                # Muito curto (ti, rh) → geral
                general_emails.add(e)
            else:
                # Verificar se parece nome (so letras, sem numeros)
                clean = prefix.replace(".", "").replace("_", "")
                if clean.isalpha() and len(clean) >= 4:
                    # Pode ser nome pessoal (ex: "fernanda") ou setor (ex: "financeiro")
                    # Se NAO tem ponto/underscore, provavelmente e setor
                    personal_emails.append(e)
                else:
                    general_emails.add(e)

        # --- Passo 2: Extrair contatos com contexto de posicao no texto ---
        lines = text.split("\n")
        line_contacts = []  # (line_index, contact_dict)

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 5:
                continue

            # Tentar formato tabular: Nome | Cargo | Email/Telefone
            # Pular linhas separadoras de tabela markdown (|---|---|)
            if re.match(r'^[\s|:-]+$', line_stripped):
                continue
            parts = re.split(r'[|\t]', line_stripped)
            # Filtrar partes vazias (comuns em tabelas markdown: | col1 | col2 |)
            parts = [p.strip().strip("*-# ") for p in parts if p.strip() and p.strip() not in ('-', '—')]
            if len(parts) >= 2:
                name_candidate = parts[0]
                role_candidate = parts[1]

                # Extrair email e telefone da linha
                line_email = None
                line_phone = None
                for p in parts[2:] if len(parts) > 2 else []:
                    p_clean = p.strip()
                    if "@" in p_clean:
                        em = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', p_clean)
                        if em:
                            line_email = em.group().rstrip(".")
                    phone_m = re.search(phone_pattern, p_clean)
                    if phone_m:
                        line_phone = re.sub(r'[^\d+]', '', phone_m.group())
                # Tambem buscar email no cargo (ex: "secretariaescolar@joaoxxiii.com")
                if not line_email and "@" in role_candidate:
                    em = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', role_candidate)
                    if em:
                        line_email = em.group().rstrip(".")

                # Decidir: pessoa ou departamento?
                is_person = self._is_valid_name(name_candidate) and self._is_valid_role(role_candidate)
                is_email_general = line_email and line_email in general_emails

                if is_person:
                    # Pessoa real — salvar sem email se o email é geral
                    name_key = name_candidate.lower()
                    if name_key not in seen_names:
                        seen_names.add(name_key)
                        person_email = line_email
                        # Nao atribuir email geral a pessoa
                        if person_email and person_email in general_emails:
                            person_email = None
                        if person_email and person_email in seen_emails:
                            person_email = None
                        if person_email:
                            seen_emails.add(person_email)
                        line_contacts.append((i, {
                            "full_name": name_candidate,
                            "role": role_candidate,
                            "email": person_email,
                            "phone": line_phone if line_phone and len(line_phone) >= 8 else None,
                            "source": "perplexity",
                            "confidence_score": 70,
                        }))
                elif line_email and line_email not in seen_emails:
                    # Nome invalido (setor, "não divulgado", etc.) + email → departamento
                    seen_emails.add(line_email)
                    general_emails.discard(line_email)
                    # Usar role como nome de departamento (mais descritivo)
                    dept_name = role_candidate if role_candidate else name_candidate
                    dept_name = re.sub(r'\([^)]*\)', '', dept_name).strip()
                    if not dept_name or len(dept_name) < 2:
                        dept_name = name_candidate
                    if not dept_name or len(dept_name) < 2:
                        prefix = line_email.split("@")[0]
                        dept_name = prefix.replace(".", " ").replace("_", " ").title()
                    line_contacts.append((i, {
                        "full_name": dept_name,
                        "role": f"Departamento ({line_email.split('@')[0]}@...)",
                        "email": line_email,
                        "phone": line_phone if line_phone and len(line_phone) >= 8 else None,
                        "source": "perplexity",
                        "confidence_score": 45,
                        "_is_general_email": True,
                    }))

        # Se nao encontrou tabular, tentar padroes livres
        if not line_contacts:
            # Pattern: **Nome Completo** - Cargo (formato markdown bold)
            # Processar linha a linha para evitar que headers capturem a proxima linha
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                # Match: **Nome** - Cargo  ou  - **Nome** - Cargo
                bold_match = re.match(r'^[*\-•\s]*\*\*([^*]+)\*\*\s*[-–:]\s*(.+)', line_stripped)
                if bold_match:
                    name_clean = bold_match.group(1).strip()
                    role_clean = bold_match.group(2).strip().rstrip(".")
                    # Limpar asteriscos, markers e emails do role
                    role_clean = re.sub(r'\*+', '', role_clean).strip()
                    role_clean = re.sub(r'\s*[-–]?\s*[\w.+-]+@[\w-]+\.[\w.]+', '', role_clean).strip()
                    role_clean = re.sub(r'\s*[-–]?\s*\(?\d{2,3}\)?\s?\d{4,5}[-.\s]?\d{4}', '', role_clean).strip()
                    if self._is_valid_name(name_clean) and self._is_valid_role(role_clean):
                        if name_clean.lower() not in seen_names:
                            seen_names.add(name_clean.lower())
                            # Extrair email e telefone da mesma linha
                            line_email = None
                            line_phone = None
                            em = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', line_stripped)
                            if em and em.group() not in general_emails:
                                line_email = em.group()
                                if line_email not in seen_emails:
                                    seen_emails.add(line_email)
                                else:
                                    line_email = None
                            pm = re.search(phone_pattern, line_stripped)
                            if pm:
                                line_phone = re.sub(r'[^\d+]', '', pm.group())
                                if len(line_phone) < 8:
                                    line_phone = None
                            line_contacts.append((i, {
                                "full_name": name_clean,
                                "role": role_clean,
                                "email": line_email,
                                "phone": line_phone,
                                "source": "perplexity",
                                "confidence_score": 60,
                            }))
                    continue

                # Pattern: Nome Completo - Cargo (sem bold)
                free_match = re.match(
                    r'^[\s*\-]*'
                    r'([A-Z][a-zA-Z\u00c0-\u00ff]+'
                    r'(?:\s+(?:de|da|do|dos|das|e|[A-Z][a-zA-Z\u00c0-\u00ff]+)){1,5})'
                    r'\s*[-\u2013,]\s*(.+)',
                    line_stripped
                )
                if free_match:
                    name_clean = free_match.group(1).strip()
                    role_clean = free_match.group(2).strip().rstrip(".")
                    if self._is_valid_name(name_clean) and self._is_valid_role(role_clean):
                        if name_clean.lower() not in seen_names:
                            seen_names.add(name_clean.lower())
                            line_contacts.append((i, {
                                "full_name": name_clean,
                                "role": role_clean,
                                "email": None,
                                "phone": None,
                                "source": "perplexity",
                                "confidence_score": 55,
                            }))

        # --- Passo 2b: Pattern inline "Nome (email), Nome (email)" ---
        # Captura nomes com email entre parenteses, separados por virgula
        # Ex: "Elaine Aragon (elaine@escola.com.br), Carolina (carol@escola.com.br)"
        inline_pattern = re.finditer(
            r'([A-Z][a-zA-Z\u00c0-\u00ff]+'
            r'(?:\s+(?:de|da|do|dos|das|e|[A-Z][a-zA-Z\u00c0-\u00ff]+)){1,4})'
            r'\s*\(([^)]*@[^)]+)\)',
            text
        )
        for m in inline_pattern:
            name_clean = m.group(1).strip()
            email_raw = m.group(2).strip().rstrip(".")
            if self._is_valid_name(name_clean) and name_clean.lower() not in seen_names:
                if email_raw not in seen_emails:
                    seen_names.add(name_clean.lower())
                    seen_emails.add(email_raw)
                    # Determinar posicao no texto
                    pos_line = text[:m.start()].count("\n")
                    is_general = any(k in email_raw.lower().split("@")[0] for k in general_keywords)
                    line_contacts.append((pos_line, {
                        "full_name": name_clean,
                        "role": "",  # sera preenchido depois se houver contexto
                        "email": email_raw if not is_general else None,
                        "phone": None,
                        "source": "perplexity",
                        "confidence_score": 65,
                        "_is_general_email": is_general,
                    }))
                    # Se email geral, adicionar como departamento separado
                    if is_general:
                        line_contacts.append((pos_line, {
                            "full_name": name_clean,
                            "role": "Departamento",
                            "email": email_raw,
                            "phone": None,
                            "source": "perplexity",
                            "confidence_score": 40,
                            "_is_general_email": True,
                        }))

        # --- Passo 3: Associar emails pessoais por PROXIMIDADE no texto ---
        # Para cada email pessoal nao usado, encontrar qual contato esta mais proximo
        unused_personal = [e for e in personal_emails if e not in seen_emails]
        for email in unused_personal:
            # Encontrar posicao do email no texto
            email_pos = text.find(email)
            if email_pos < 0:
                continue
            email_line = text[:email_pos].count("\n")

            # Encontrar contato mais proximo (por distancia de linhas)
            best_ct = None
            best_dist = 999
            for line_idx, ct in line_contacts:
                if ct.get("email"):
                    continue  # ja tem email
                dist = abs(line_idx - email_line)
                if dist < best_dist:
                    best_dist = dist
                    best_ct = ct

            # So associar se esta dentro de 3 linhas de distancia
            if best_ct and best_dist <= 3:
                best_ct["email"] = email
                seen_emails.add(email)

        # --- Passo 4: Associar telefones por proximidade ---
        # Re-extrair telefones com posicao original no texto (nao so digitos)
        phone_with_pos = list(re.finditer(phone_pattern, text))
        assigned_phones = set(ct.get("phone") for _, ct in line_contacts if ct.get("phone"))

        for pm in phone_with_pos:
            clean_phone = re.sub(r'[^\d+]', '', pm.group())
            if len(clean_phone) < 8 or clean_phone in assigned_phones:
                continue
            phone_line = text[:pm.start()].count("\n")

            best_ct = None
            best_dist = 999
            for line_idx, ct in line_contacts:
                if ct.get("phone"):
                    continue
                dist = abs(line_idx - phone_line)
                if dist < best_dist:
                    best_dist = dist
                    best_ct = ct

            if best_ct and best_dist <= 3:
                best_ct["phone"] = clean_phone
                assigned_phones.add(clean_phone)

        # Montar lista final
        contacts = [ct for _, ct in line_contacts]

        # --- Passo 5: Emails gerais → contato de departamento (nunca pessoa) ---
        for email in general_emails:
            if email in seen_emails:
                continue
            seen_emails.add(email)
            prefix = email.split("@")[0].lower()
            # Mapear prefixo para departamento
            dept_map = {
                "diretor": "Diretoria", "diretoria": "Diretoria",
                "coord": "Coordenacao Pedagogica", "pedagog": "Coordenacao Pedagogica",
                "secretaria": "Secretaria", "secret": "Secretaria",
                "financeiro": "Financeiro", "tesouraria": "Financeiro",
                "matricula": "Secretaria de Matriculas", "matriculas": "Secretaria de Matriculas",
                "rh": "Recursos Humanos",
                "comunicacao": "Comunicacao", "marketing": "Comunicacao",
                "biblioteca": "Biblioteca",
            }
            dept = "Contato Geral"
            for key, label in dept_map.items():
                if key in prefix:
                    dept = label
                    break

            contacts.append({
                "full_name": dept,
                "role": f"Departamento ({prefix}@...)",
                "email": email,
                "phone": None,
                "source": "perplexity",
                "confidence_score": 40,
                "_is_general_email": True,
            })

        # --- Passo 6: Deduzir emails pessoais por padrao ---
        import unicodedata

        def _remove_accents(s):
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

        personal_found = [ct for ct in contacts
                          if ct.get("email") and not ct.get("_is_general_email")]

        # Determinar dominio e padrao
        domain = ""
        pattern_type = None

        if personal_found:
            # Caso A: temos email pessoal → detectar padrao exato
            sample = personal_found[0]["email"]
            domain = sample.split("@")[1] if "@" in sample else ""
            prefix = sample.split("@")[0].lower() if "@" in sample else ""
            sample_name = _remove_accents(personal_found[0].get("full_name", ""))

            if "." in prefix:
                parts_p = prefix.split(".")
                name_parts = sample_name.split()
                if len(parts_p) == 2 and len(name_parts) >= 2:
                    first_n = _remove_accents(name_parts[0])
                    last_n = _remove_accents(name_parts[-1])
                    if parts_p[0] == first_n and parts_p[1] == last_n:
                        pattern_type = "nome.sobrenome"
                    elif parts_p[0] == first_n[:1] and parts_p[1] == last_n:
                        pattern_type = "inicial.sobrenome"
                    elif parts_p[0] == first_n:
                        pattern_type = "nome.sobrenome"
            elif prefix == sample_name.split()[0] if sample_name else "":
                pattern_type = "nome"
        else:
            # Caso B: sem email pessoal → extrair dominio dos departamentos
            # e sugerir padrao mais comum (nome.sobrenome)
            dept_emails = [ct.get("email") for ct in contacts
                           if ct.get("email") and ct.get("_is_general_email")]
            if dept_emails:
                domain = dept_emails[0].split("@")[1] if "@" in dept_emails[0] else ""
                pattern_type = "nome.sobrenome"  # padrao mais comum

        # Aplicar sugestoes
        if pattern_type and domain:
            people_without_email = [ct for ct in contacts
                                    if not ct.get("email") and not ct.get("_is_general_email")
                                    and self._is_valid_name(ct.get("full_name", ""))]
            for ct in people_without_email:
                name = ct.get("full_name", "")
                name_parts = name.split()
                if len(name_parts) < 2:
                    continue
                first = _remove_accents(name_parts[0])
                last = _remove_accents(name_parts[-1])
                if pattern_type == "nome.sobrenome":
                    suggested = f"{first}.{last}@{domain}"
                elif pattern_type == "inicial.sobrenome":
                    suggested = f"{first[0]}.{last}@{domain}"
                elif pattern_type == "nome":
                    suggested = f"{first}@{domain}"
                else:
                    continue
                ct["_suggested_email"] = suggested
                # Confidence menor quando nao temos email de referencia
                confidence = 30 if personal_found else 20
                ct["confidence_score"] = max(ct.get("confidence_score", 0), confidence)

        return contacts[:50]


# Singleton
perplexity_browser = PerplexityBrowser()
