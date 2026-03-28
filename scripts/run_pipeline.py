"""run_pipeline.py - CLI para executar o pipeline manualmente."""
import sys, argparse
from pathlib import Path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from workflows.daily_pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="Pipeline IAprendo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qualify", type=int, default=20)
    parser.add_argument("--enrich", type=int, default=10)
    parser.add_argument("--write", type=int, default=10)
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()
    sep = "=" * 60
    print(sep)
    print("IAprendo Sales Agent - Pipeline")
    if args.dry_run:
        print("[DRY-RUN] Simulando sem acoes reais")
    print(sep)
    result = run_pipeline(
        qualify_limit=args.qualify,
        enrich_limit=args.enrich,
        write_limit=args.write,
        send_approved=not args.no_send,
        dry_run=args.dry_run,
    )
    s = result.get("summary", {})
    print(sep)
    print("RESUMO:")
    print("  Escolas qualificadas:", s.get("qualified", 0))
    print("  Mensagens geradas:", s.get("messages_generated", 0))
    print("  Mensagens enviadas:", s.get("messages_sent", 0))
    print(sep)

if __name__ == "__main__":
    main()