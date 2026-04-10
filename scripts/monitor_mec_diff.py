"""
Monitor de mudancas na base MEC (Censo + Catalogo INEP).

Compara o estado atual da base mesclada (`escolas_brasil_merged.csv`) com
um snapshot anterior salvo em disco e gera um relatorio de delta:

- Escolas NOVAS (CO_INEP que nao existiam antes)
- Escolas REMOVIDAS (CO_INEP que sumiram)
- Escolas com MUDANCAS RELEVANTES em matriculas (>= 10%)
- Escolas que mudaram de status (Censo 2025 -> Catalogo INEP ou vice-versa)

Uso:
    # Snapshot inicial (so cria, sem comparar)
    venv/Scripts/python.exe scripts/monitor_mec_diff.py --snapshot

    # Comparar com snapshot anterior
    venv/Scripts/python.exe scripts/monitor_mec_diff.py --diff

    # Comparar e salvar novo snapshot
    venv/Scripts/python.exe scripts/monitor_mec_diff.py --diff --update

    # JSON puro (para uso programatico)
    venv/Scripts/python.exe scripts/monitor_mec_diff.py --diff --json

Quando rodar:
- Manualmente sempre que receber nova versao do CSV do MEC
- Idealmente apos cada novo Censo Escolar (anual)
- Apos rodar `merge_catalogo_inep.py` (que regenera o merged.csv)

Saida:
- Relatorio em texto (default) ou JSON (--json)
- Snapshot salvo em `data/processed/mec_snapshot_YYYY-MM-DD.json`
"""
import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from config.settings import settings

CSV_PATH = ROOT / settings.CSV_PATH
SNAPSHOT_DIR = ROOT / "data" / "processed"


def load_current_csv() -> pd.DataFrame:
    """Carrega o CSV mesclado atual."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV nao encontrado em {CSV_PATH}. Rode merge_catalogo_inep.py primeiro."
        )
    df = pd.read_csv(CSV_PATH, encoding=settings.CSV_ENCODING, low_memory=False)
    return df


def to_snapshot_dict(df: pd.DataFrame) -> dict:
    """Converte DataFrame em dict {inep: snapshot} para comparacao rapida."""
    snapshot = {}
    for _, row in df.iterrows():
        inep = str(row.get("CODIGO_INEP", "")).strip()
        if not inep or inep == "nan":
            continue
        snapshot[inep] = {
            "name": str(row.get("NOME_ESCOLA", "")),
            "uf": str(row.get("UF", "")),
            "city": str(row.get("MUNICIPIO", "")),
            "fonte": str(row.get("FONTE_DADOS", "")),
            "total_mat": int(row.get("TOTAL_MATRICULAS") or 0) if pd.notna(row.get("TOTAL_MATRICULAS")) else 0,
            "fund_af": int(row.get("MATRICULAS_FUND_AF") or 0) if pd.notna(row.get("MATRICULAS_FUND_AF")) else 0,
            "medio": int(row.get("MATRICULAS_MEDIO") or 0) if pd.notna(row.get("MATRICULAS_MEDIO")) else 0,
        }
    return snapshot


def latest_snapshot_path() -> Path | None:
    """Retorna o caminho do snapshot mais recente, ou None."""
    if not SNAPSHOT_DIR.exists():
        return None
    snapshots = sorted(SNAPSHOT_DIR.glob("mec_snapshot_*.json"))
    return snapshots[-1] if snapshots else None


def save_snapshot(snapshot: dict) -> Path:
    """Salva snapshot atual em disco."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = SNAPSHOT_DIR / f"mec_snapshot_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "data": today,
            "total": len(snapshot),
            "escolas": snapshot,
        }, f, ensure_ascii=False)
    return path


def load_snapshot(path: Path) -> dict:
    """Carrega snapshot anterior."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("escolas", {})


def compute_diff(old: dict, new: dict, threshold_pct: float = 10.0) -> dict:
    """Compara dois snapshots e retorna delta.

    Args:
        old: snapshot antigo {inep: {...}}
        new: snapshot novo {inep: {...}}
        threshold_pct: % minimo de mudanca em matriculas para reportar

    Returns:
        Dict com listas de mudancas categorizadas.
    """
    old_ids = set(old.keys())
    new_ids = set(new.keys())

    novas_ids = new_ids - old_ids
    removidas_ids = old_ids - new_ids
    mantidas_ids = old_ids & new_ids

    # Escolas novas
    novas = [
        {
            "inep": inep,
            "name": new[inep]["name"],
            "city": new[inep]["city"],
            "uf": new[inep]["uf"],
            "fonte": new[inep]["fonte"],
            "alvo": new[inep]["fund_af"] + new[inep]["medio"],
        }
        for inep in sorted(novas_ids)
    ]

    # Escolas removidas
    removidas = [
        {
            "inep": inep,
            "name": old[inep]["name"],
            "city": old[inep]["city"],
            "uf": old[inep]["uf"],
            "fonte": old[inep]["fonte"],
            "alvo": old[inep]["fund_af"] + old[inep]["medio"],
        }
        for inep in sorted(removidas_ids)
    ]

    # Mudancas em matriculas (>= threshold%)
    mudancas_matriculas = []
    mudancas_fonte = []
    for inep in mantidas_ids:
        o = old[inep]
        n = new[inep]

        # Mudou de fonte (ex: catalogo -> censo)
        if o["fonte"] != n["fonte"]:
            mudancas_fonte.append({
                "inep": inep,
                "name": n["name"],
                "fonte_antiga": o["fonte"],
                "fonte_nova": n["fonte"],
            })

        # Mudou matricula total (>= threshold%)
        old_total = o["total_mat"]
        new_total = n["total_mat"]
        if old_total > 0:
            delta_pct = ((new_total - old_total) / old_total) * 100.0
            if abs(delta_pct) >= threshold_pct:
                mudancas_matriculas.append({
                    "inep": inep,
                    "name": n["name"],
                    "city": n["city"],
                    "old_total": old_total,
                    "new_total": new_total,
                    "delta_pct": round(delta_pct, 1),
                })
        elif new_total > 0:
            # Antes era 0, agora tem alunos — caso especial
            mudancas_matriculas.append({
                "inep": inep,
                "name": n["name"],
                "city": n["city"],
                "old_total": 0,
                "new_total": new_total,
                "delta_pct": None,
            })

    # Ordenar mudancas por magnitude
    mudancas_matriculas.sort(
        key=lambda x: abs(x.get("delta_pct") or 999),
        reverse=True,
    )

    return {
        "total_old": len(old),
        "total_new": len(new),
        "delta_total": len(new) - len(old),
        "novas": novas,
        "removidas": removidas,
        "mudancas_matriculas": mudancas_matriculas,
        "mudancas_fonte": mudancas_fonte,
    }


def format_report(diff: dict) -> str:
    """Formata relatorio em texto legivel."""
    lines = []
    lines.append("=" * 70)
    lines.append("RELATORIO DE MUDANCAS NA BASE MEC")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Total anterior: {diff['total_old']:,}".replace(",", "."))
    lines.append(f"Total atual: {diff['total_new']:,}".replace(",", "."))
    delta = diff["delta_total"]
    sinal = "+" if delta >= 0 else ""
    lines.append(f"Delta: {sinal}{delta:,}".replace(",", "."))
    lines.append("")

    # Novas
    lines.append(f"=== ESCOLAS NOVAS: {len(diff['novas'])} ===")
    for n in diff["novas"][:20]:
        lines.append(f"  + [{n['inep']}] {n['name'][:45]} | {n['city']}/{n['uf']} | alvo={n['alvo']} | {n['fonte']}")
    if len(diff["novas"]) > 20:
        lines.append(f"  ... e mais {len(diff['novas']) - 20} escolas")
    lines.append("")

    # Removidas
    lines.append(f"=== ESCOLAS REMOVIDAS: {len(diff['removidas'])} ===")
    for r in diff["removidas"][:20]:
        lines.append(f"  - [{r['inep']}] {r['name'][:45]} | {r['city']}/{r['uf']} | era {r['fonte']}")
    if len(diff["removidas"]) > 20:
        lines.append(f"  ... e mais {len(diff['removidas']) - 20} escolas")
    lines.append("")

    # Mudancas de fonte
    lines.append(f"=== MUDANCAS DE FONTE: {len(diff['mudancas_fonte'])} ===")
    for m in diff["mudancas_fonte"][:10]:
        lines.append(f"  ~ [{m['inep']}] {m['name'][:40]} | {m['fonte_antiga']} -> {m['fonte_nova']}")
    if len(diff["mudancas_fonte"]) > 10:
        lines.append(f"  ... e mais {len(diff['mudancas_fonte']) - 10}")
    lines.append("")

    # Mudancas de matriculas
    lines.append(f"=== MUDANCAS EM MATRICULAS (>= 10%): {len(diff['mudancas_matriculas'])} ===")
    for m in diff["mudancas_matriculas"][:20]:
        delta_str = f"{m['delta_pct']:+.1f}%" if m['delta_pct'] is not None else "novo"
        lines.append(f"  ~ {m['name'][:40]} | {m['old_total']} -> {m['new_total']} ({delta_str})")
    if len(diff["mudancas_matriculas"]) > 20:
        lines.append(f"  ... e mais {len(diff['mudancas_matriculas']) - 20}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true",
                        help="Apenas salva snapshot atual (sem comparar)")
    parser.add_argument("--diff", action="store_true",
                        help="Compara com ultimo snapshot e mostra relatorio")
    parser.add_argument("--update", action="store_true",
                        help="Apos diff, sobrescreve com novo snapshot")
    parser.add_argument("--json", action="store_true",
                        help="Saida em JSON puro (para uso programatico)")
    parser.add_argument("--threshold", type=float, default=10.0,
                        help="Pct minimo de mudanca em matriculas para reportar (default 10)")
    args = parser.parse_args()

    if not args.snapshot and not args.diff:
        parser.print_help()
        return

    print(f"Carregando CSV atual ({CSV_PATH.name})...")
    df = load_current_csv()
    print(f"  {len(df):,} escolas".replace(",", "."))

    snapshot_atual = to_snapshot_dict(df)

    if args.snapshot:
        path = save_snapshot(snapshot_atual)
        print(f"\nSnapshot salvo em: {path}")
        return

    # diff
    last_path = latest_snapshot_path()
    if not last_path:
        print("\nNenhum snapshot anterior encontrado.")
        print("Salvando snapshot inicial...")
        path = save_snapshot(snapshot_atual)
        print(f"Snapshot salvo em: {path}")
        print("Rode novamente apos receber nova versao do CSV.")
        return

    print(f"\nComparando com snapshot: {last_path.name}")
    snapshot_anterior = load_snapshot(last_path)

    diff = compute_diff(snapshot_anterior, snapshot_atual, threshold_pct=args.threshold)

    if args.json:
        print(json.dumps(diff, ensure_ascii=False, default=str))
    else:
        print()
        print(format_report(diff))

    if args.update:
        path = save_snapshot(snapshot_atual)
        print(f"\nSnapshot atualizado: {path}")


if __name__ == "__main__":
    main()
