"""
generate_onboarding_pdf.py - Gera o Guia de Inicio Rapido (PDF) pro time comercial.

Reutilizavel: rode de novo quando o sistema mudar pra regenerar o guia.
    venv\\Scripts\\python.exe scripts\\generate_onboarding_pdf.py

Saida: data/exports/Onboarding_IAprendo_Guia_Rapido.pdf

Sem emojis (as fontes embutidas do reportlab nao tem esses glifos). Acentos do
portugues funcionam normalmente (Latin-1/WinAnsi).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, KeepTogether,
)

# ----------------------------------------------------------------- paleta
BLUE = colors.HexColor("#2563EB")
DARK = colors.HexColor("#1E293B")
GRAY = colors.HexColor("#64748B")
LIGHT = colors.HexColor("#F1F5F9")
LINE = colors.HexColor("#E2E8F0")
GREEN = colors.HexColor("#16A34A")
GREENBG = colors.HexColor("#DCFCE7")
AMBER = colors.HexColor("#B45309")
AMBERBG = colors.HexColor("#FEF3C7")

OUT = ROOT / "data" / "exports" / "Onboarding_IAprendo_Guia_Rapido.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

APP_URL = "vendasiaprendo.duogen.com.br"

# ----------------------------------------------------------------- estilos
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                    fontSize=15, textColor=BLUE, spaceBefore=14, spaceAfter=6, leading=18)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                    fontSize=11.5, textColor=DARK, spaceBefore=8, spaceAfter=3, leading=14)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontName="Helvetica",
                      fontSize=10, textColor=DARK, leading=14.5, spaceAfter=4)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.5, textColor=GRAY, leading=11)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=2, spaceAfter=2)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=9, leading=12, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")
CALL = ParagraphStyle("CALL", parent=BODY, fontSize=9.5, leading=13.5, spaceAfter=0)
TITLE = ParagraphStyle("TITLE", parent=ss["Title"], fontName="Helvetica-Bold",
                       fontSize=24, textColor=DARK, spaceAfter=2, leading=27)
SUBT = ParagraphStyle("SUBT", parent=BODY, fontSize=12, textColor=GRAY, spaceAfter=2)


def bullets(items, style=BULLET):
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=12, value="•") for t in items],
        bulletType="bullet", start="•", leftIndent=14, bulletColor=BLUE,
    )


def callout(title, body_html, bg, bar):
    """Caixa de destaque (1 celula) com barra colorida a esquerda."""
    inner = []
    if title:
        inner.append(Paragraph(f"<b>{title}</b>", ParagraphStyle(
            "CT", parent=CALL, textColor=bar, spaceAfter=3)))
    inner.append(Paragraph(body_html, CALL))
    t = Table([[inner]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def kv_table(rows, c0=42 * mm, c1=128 * mm):
    data = [[Paragraph(k, CELLB), Paragraph(v, CELL)] for k, v in rows]
    t = Table(data, colWidths=[c0, c1])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def two_col_table(header, rows, c0=46 * mm, c1=124 * mm):
    data = [[Paragraph(header[0], CELLB), Paragraph(header[1], CELLB)]]
    data += [[Paragraph(a, CELLB), Paragraph(b, CELL)] for a, b in rows]
    t = Table(data, colWidths=[c0, c1], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    # header bold white
    for i in range(len(data)):
        pass
    return t


def _chrome(canvas, doc):
    canvas.saveState()
    # faixa superior
    canvas.setFillColor(BLUE)
    canvas.rect(0, A4[1] - 16 * mm, A4[0], 16 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(18 * mm, A4[1] - 10.5 * mm, "IAprendo Sales Agent")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 10.5 * mm, "Guia de Inicio Rapido")
    # rodape
    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 9 * mm, "DUOGEN | IAprendo - uso interno")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Pagina {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
    canvas.restoreState()


def build():
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=16 * mm,
        title="IAprendo Sales Agent - Guia de Inicio Rapido",
        author="DUOGEN / IAprendo",
    )
    s = []

    # ---------------------------------------------------------- titulo
    s.append(Paragraph("Guia de Inicio Rapido", TITLE))
    s.append(Paragraph("IAprendo Sales Agent &mdash; para o time comercial", SUBT))
    s.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=6, spaceAfter=8))
    s.append(Paragraph(
        "Bem-vindo(a) ao time! Este guia te coloca operando em poucos minutos. "
        "A plataforma e um CRM com IA (o <b>IAlex</b>) para prospeccao de escolas: "
        "ela ajuda a achar leads, qualificar, escrever emails personalizados e "
        "acompanhar tudo &mdash; sempre com a sua aprovacao antes de enviar. "
        "Para o passo a passo completo, use a pagina <b>Manual</b> dentro do sistema.", BODY))

    # ---------------------------------------------------------- 1. acesso
    s.append(Paragraph("1. Acesso (login)", H1))
    s.append(kv_table([
        ("Endereco", f"<b>https://{APP_URL}</b> (abra no navegador; pode salvar nos favoritos)"),
        ("Usuario", "seu primeiro nome em minusculas &mdash; ex: <b>lizianne</b>, <b>felipe</b>"),
        ("Senha", "a que o Fernando te enviou em particular"),
        ("1o acesso", "troque a senha na barra lateral &rarr; <b>Trocar senha</b>"),
    ]))
    s.append(Spacer(1, 4))
    s.append(Paragraph(
        "A plataforma identifica quem voce e pelo login: seu nome e assinatura entram "
        "automaticamente nos emails que voce enviar.", SMALL))

    # ---------------------------------------------------------- 2. mapa
    s.append(Paragraph("2. Mapa rapido das paginas", H1))
    s.append(two_col_table(("Pagina", "Para que serve"), [
        ("Chat IAlex", "Conversar com a IA (1a pagina). Pede em portugues: buscar, qualificar, gerar email, exportar planilha."),
        ("Escolas", "O CRM: lista de escolas, detalhe, performance ENEM, registrar contato."),
        ("Contatos", "Decisores de cada escola (diretor, coordenador) com email/telefone."),
        ("Mapa", "Escolas no mapa (geografico)."),
        ("Importar", "Trazer escolas novas da base do MEC (busca por nome/cidade/UF) para o CRM."),
        ("Pipeline", "Onde a prospeccao acontece: qualificar, enriquecer, achar contatos, gerar email."),
        ("Comunicacao", "APROVAR emails, follow-ups, templates e metricas."),
        ("Inteligencia", "Ranking de leads por ENEM e comparativos."),
        ("Analytics", "Numeros: funil, conversoes, custos."),
        ("Manual", "Guia completo da plataforma (12 abas)."),
    ]))

    # ---------------------------------------------------------- 3. fluxo
    s.append(Paragraph("3. Seu fluxo do dia a dia", H1))
    s.append(Paragraph(
        "O caminho de uma escola ate virar um contato comercial:", BODY))
    steps = [
        ("1. Achar a escola",
         "Em <b>Importar &rarr; Busca Online</b> procure por nome/cidade/UF e importe "
         "as que quiser; ou trabalhe as que ja estao em <b>Escolas</b>."),
        ("2. Preparar o lead",
         "Em <b>Pipeline &rarr; Execucao</b>, selecione a(s) escola(s) e rode: "
         "<b>Qualificar</b> (a IA da uma nota), <b>Enriquecer</b> e <b>Encontrar Contatos</b>."),
        ("3. Gerar o email",
         "Ainda no Pipeline, clique <b>Gerar Email</b>. Escolha o modo: <b>IA "
         "personalizada</b> (recomendado) ou <b>Template</b>."),
        ("4. Aprovar e enviar",
         "Va em <b>Comunicacao &rarr; Aprovacao</b>, leia o email e escolha: Aprovar, "
         "Editar+Aprovar, Reescrever ou Rejeitar. So depois de aprovar ele e enviado."),
        ("5. Acompanhar",
         "O sistema rastreia entregue &rarr; aberto &rarr; clicado &rarr; respondeu, e "
         "sugere follow-ups. Veja em <b>Comunicacao</b>."),
        ("6. Registrar contatos manuais",
         "Ligou ou falou no WhatsApp pessoal? Registre em <b>Escolas &rarr; (abrir a "
         "escola) &rarr; Registrar Contato</b> para o time ter o historico."),
    ]
    for title, body in steps:
        s.append(Paragraph(f"<b>{title}</b>", H2))
        s.append(Paragraph(body, BODY))

    s.append(Spacer(1, 4))
    s.append(callout(
        "Regra de ouro: nada e enviado sem a sua aprovacao",
        "Nenhum email sai automaticamente. Tudo passa pela tela de "
        "<b>Aprovacao</b> &mdash; voce le e decide. Isso protege a marca e a "
        "qualidade de cada abordagem.",
        AMBERBG, AMBER))

    # ---------------------------------------------------------- 4. ownership
    s.append(Paragraph("4. Dono do lead (para nao pisar no pe um do outro)", H1))
    s.append(Paragraph(
        "Voces tres compartilham o mesmo CRM. Para evitar duas pessoas abordando a "
        "mesma escola:", BODY))
    s.append(bullets([
        "<b>A acao define o dono.</b> Quando voce envia um email, registra um contato "
        "ou manda WhatsApp para uma escola sem dono, ela passa a ser <b>sua</b>. "
        "Nao existe botao de “reservar” &mdash; quem trabalha o lead vira o dono.",
        "<b>Todos enxergam</b> a marca “Sob gestao de [nome]” na escola, no "
        "Pipeline e em Contatos.",
        "<b>Aviso, nao bloqueio.</b> Se voce for agir numa escola de outra pessoa, "
        "aparece um aviso para confirmar. Combine com o colega antes de seguir.",
    ]))

    # ---------------------------------------------------------- 5. IAlex
    s.append(Paragraph("5. IAlex &mdash; o atalho (IA)", H1))
    s.append(Paragraph(
        "O jeito mais rapido de operar: fale com o IAlex em linguagem natural, pelo "
        "<b>Chat IAlex</b> (1a pagina) ou pelo <b>WhatsApp</b> &mdash; mesmo cerebro. "
        "Exemplos do que pedir:", BODY))
    s.append(two_col_table(("Voce pede...", "...e o IAlex faz"), [
        ("“busca escolas privadas de ensino medio em Porto Alegre”",
         "Lista escolas da base completa do MEC."),
        ("“importa o Colegio Anchieta pro CRM”", "Traz a escola pro CRM."),
        ("“qualifica e gera email pro Colegio X”", "Roda o pipeline e cria o email (vai pra aprovacao)."),
        ("“registra que liguei pra diretora da escola Y hoje”", "Loga o contato no historico."),
        ("“gera um excel das escolas de POA com ensino medio”", "Entrega uma planilha para download."),
        ("“o que voce sabe fazer?”", "Lista as capacidades."),
    ]))
    s.append(Spacer(1, 3))
    s.append(Paragraph(
        "Dica: seja direto (“qualifique a escola X”). Mesmo pelo IAlex, "
        "emails sempre passam pela sua aprovacao.", SMALL))

    # ---------------------------------------------------------- 6. regras + ajuda
    s.append(Paragraph("6. Regras de ouro e ajuda", H1))
    s.append(callout(
        "Lembre sempre",
        "1) <b>Nada e enviado sem aprovacao.</b> &nbsp; "
        "2) <b>Personalize</b> &mdash; nada de mensagem generica. &nbsp; "
        "3) <b>Combine com o time</b> antes de abordar escola de outro dono. &nbsp; "
        "4) Em duvida, abra a pagina <b>Manual</b> (guia completo).",
        GREENBG, GREEN))
    s.append(Spacer(1, 6))
    s.append(kv_table([
        ("Manual completo", "Pagina <b>Manual</b> dentro da plataforma (12 abas, com fluxograma e glossario)."),
        ("Suporte", "Fale com o <b>Fernando</b> (admin) para acesso, senha ou duvidas."),
    ]))

    doc.build(s, onFirstPage=_chrome, onLaterPages=_chrome)
    print(f"OK - PDF gerado: {OUT}")
    print(f"     ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
