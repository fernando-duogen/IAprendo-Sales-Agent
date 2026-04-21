/**
 * Cloudflare Worker: dados.iaprendo.com.br
 *
 * 2 responsabilidades:
 * 1. GET /reports/{inep}.html → proxy para Supabase Storage (OPR HTML)
 * 2. POST /track-opr           → grava evento em opr_pageviews (tracking)
 *
 * Deploy: Cloudflare Dashboard → Workers & Pages → Edit existing worker
 * Route:  dados.iaprendo.com.br/*
 *
 * Secrets necessarios (Cloudflare → Settings → Variables):
 *   - SUPABASE_URL        = https://vgmvpghwkeirnjdbjcwl.supabase.co
 *   - SUPABASE_ANON_KEY   = chave anon publica (pode ser commitada — e feita pra isso)
 */

const SUPABASE_STORAGE_BASE =
  "https://vgmvpghwkeirnjdbjcwl.supabase.co/storage/v1/object/public/insight-charts";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "3600",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // ============================================================
    // 1. TRACK-OPR — recebe eventos de tracking do HTML
    // ============================================================
    if (path === "/track-opr") {
      // CORS preflight
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: CORS_HEADERS });
      }

      if (request.method !== "POST") {
        return jsonResponse({ error: "method not allowed" }, 405);
      }

      try {
        const data = await request.json();
        const inep = String(data.inep || "").trim();
        if (!inep) {
          return jsonResponse({ error: "inep required" }, 400);
        }

        // Hash do IP (privacidade / LGPD)
        const ip = request.headers.get("CF-Connecting-IP") || "";
        const ipHash = ip ? (await sha256(ip)).substring(0, 32) : "";

        // Resolver company_id (opcional, fail-safe)
        let companyId = null;
        try {
          const compResp = await fetch(
            `${env.SUPABASE_URL}/rest/v1/companies?inep_code=eq.${inep}&select=id&limit=1`,
            {
              headers: {
                apikey: env.SUPABASE_ANON_KEY,
                Authorization: `Bearer ${env.SUPABASE_ANON_KEY}`,
              },
            }
          );
          if (compResp.ok) {
            const compData = await compResp.json();
            if (compData.length > 0) companyId = compData[0].id;
          }
        } catch (e) {
          /* continua sem company_id */
        }

        // Insert no opr_pageviews
        const insertResp = await fetch(
          `${env.SUPABASE_URL}/rest/v1/opr_pageviews`,
          {
            method: "POST",
            headers: {
              apikey: env.SUPABASE_ANON_KEY,
              Authorization: `Bearer ${env.SUPABASE_ANON_KEY}`,
              "Content-Type": "application/json",
              Prefer: "return=minimal",
            },
            body: JSON.stringify({
              inep,
              company_id: companyId,
              event_type: String(data.event || "page_load").substring(0, 30),
              benchmark_viewed: data.benchmark || null,
              session_id: String(data.session_id || "").substring(0, 64),
              user_agent: (request.headers.get("User-Agent") || "").substring(0, 500),
              referer: (request.headers.get("Referer") || "").substring(0, 500),
              ip_hash: ipHash,
            }),
          }
        );

        if (!insertResp.ok) {
          const errText = await insertResp.text();
          return jsonResponse(
            { error: "supabase insert failed", detail: errText.substring(0, 200) },
            500
          );
        }

        return jsonResponse({ ok: true });
      } catch (err) {
        return jsonResponse({ error: String(err).substring(0, 200) }, 500);
      }
    }

    // ============================================================
    // 2. PAGINA INICIAL — redireciona para site principal
    // ============================================================
    if (path === "/" || path === "") {
      return Response.redirect("https://iaprendo.com.br", 302);
    }

    // ============================================================
    // 3. PROXY PARA SUPABASE STORAGE (OPR HTML + PNGs)
    // ============================================================
    const targetUrl = `${SUPABASE_STORAGE_BASE}${path}`;

    try {
      const response = await fetch(targetUrl, {
        method: request.method,
        headers: {
          "User-Agent": "IAprendo-Proxy/1.0",
        },
      });

      if (!response.ok) {
        return new Response(
          `<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2>Conteudo nao encontrado</h2>
            <p>O relatorio solicitado nao esta disponivel.</p>
            <a href="https://iaprendo.com.br">Voltar para IAprendo</a>
          </body></html>`,
          {
            status: 404,
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }
        );
      }

      // Copiar response com headers corretos
      const newHeaders = new Headers(response.headers);
      newHeaders.set("Access-Control-Allow-Origin", "*");
      newHeaders.set("X-Powered-By", "IAprendo");

      // Remover Content-Security-Policy sandbox do Supabase (bloqueia CSS/JS inline)
      newHeaders.delete("Content-Security-Policy");

      // Garantir Content-Type correto (Supabase pode servir como text/plain)
      if (path.endsWith(".html")) {
        newHeaders.set("Content-Type", "text/html; charset=utf-8");
      } else if (path.endsWith(".png")) {
        newHeaders.set("Content-Type", "image/png");
      }

      return new Response(response.body, {
        status: response.status,
        headers: newHeaders,
      });
    } catch (err) {
      return new Response("Erro interno", { status: 500 });
    }
  },
};

// ============================================================
// Helpers
// ============================================================

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...CORS_HEADERS,
    },
  });
}

async function sha256(str) {
  const msgBuffer = new TextEncoder().encode(str);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}
