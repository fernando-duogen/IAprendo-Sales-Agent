-- Migration 016: OPR Pageviews — tracking de acessos aos relatorios
-- Cada view de OPR (page_load, tab_click, cta_click) gera um registro.
-- Permite saber: quem abriu, qual benchmark viu, quantas vezes voltou.

CREATE TABLE IF NOT EXISTS opr_pageviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inep VARCHAR(20) NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    event_type VARCHAR(30) NOT NULL,       -- 'page_load', 'tab_click', 'cta_click'
    benchmark_viewed VARCHAR(20),          -- 'Estadual', 'Municipal', 'Federal', 'Privada'
    session_id VARCHAR(64),                -- localStorage UUID (agrupa eventos do mesmo visitante)
    user_agent TEXT,
    referer TEXT,
    ip_hash VARCHAR(64),                   -- SHA256 do IP (privacidade)
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opr_pv_inep_time ON opr_pageviews(inep, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_opr_pv_company ON opr_pageviews(company_id, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_opr_pv_session ON opr_pageviews(session_id);
CREATE INDEX IF NOT EXISTS idx_opr_pv_event ON opr_pageviews(event_type, viewed_at DESC);

-- View util: resumo por OPR
CREATE OR REPLACE VIEW opr_pageviews_summary AS
SELECT
    p.inep,
    c.name AS company_name,
    c.city,
    c.state,
    COUNT(*) AS total_events,
    COUNT(DISTINCT p.session_id) AS unique_sessions,
    COUNT(*) FILTER (WHERE p.event_type = 'page_load') AS page_loads,
    COUNT(*) FILTER (WHERE p.event_type = 'tab_click') AS tab_clicks,
    COUNT(*) FILTER (WHERE p.event_type = 'cta_click') AS cta_clicks,
    MAX(p.viewed_at) AS last_viewed_at,
    MIN(p.viewed_at) AS first_viewed_at,
    -- Aba mais visualizada
    MODE() WITHIN GROUP (ORDER BY p.benchmark_viewed)
        FILTER (WHERE p.benchmark_viewed IS NOT NULL) AS most_viewed_benchmark
FROM opr_pageviews p
LEFT JOIN companies c ON c.id = p.company_id
GROUP BY p.inep, c.name, c.city, c.state;

COMMENT ON TABLE opr_pageviews IS 'Tracking de acessos a OPRs (F7 - Dashboard Evolution). Cada evento e um registro.';
COMMENT ON COLUMN opr_pageviews.event_type IS 'page_load, tab_click, cta_click';
COMMENT ON COLUMN opr_pageviews.benchmark_viewed IS 'Qual aba foi ativada (Estadual/Municipal/Federal/Privada)';
COMMENT ON COLUMN opr_pageviews.session_id IS 'UUID gerado no browser (localStorage), persiste entre visitas';
COMMENT ON COLUMN opr_pageviews.ip_hash IS 'SHA256 do IP (LGPD-compliant, sem identificar o usuario)';
