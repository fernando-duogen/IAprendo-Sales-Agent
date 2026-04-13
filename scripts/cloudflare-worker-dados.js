/**
 * Cloudflare Worker: dados.iaprendo.com.br → Supabase Storage proxy
 *
 * Redireciona requests de dados.iaprendo.com.br/reports/{inep}.html
 * para o Supabase Storage, mantendo a URL profissional.
 *
 * Deploy: Cloudflare Dashboard → Workers & Pages → Create Worker
 * Route: dados.iaprendo.com.br/*
 */

const SUPABASE_STORAGE_BASE =
  "https://vgmvpghwkeirnjdbjcwl.supabase.co/storage/v1/object/public/insight-charts";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Pagina inicial: redireciona para o site principal
    if (path === "/" || path === "") {
      return Response.redirect("https://iaprendo.com.br", 302);
    }

    // Proxy para Supabase Storage
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
