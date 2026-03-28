"""
Backup Manager - Exporta dados do Supabase para CSV local.
Backup automatico ou manual.

Permite exportar tabelas individuais ou todas de uma vez,
gerar relatorios resumidos e limpar backups antigos.

Classes:
    BackupManager: Gerenciador de backups com export para CSV

Usage:
    from tools.backup_manager import backup_manager

    # Backup de uma tabela
    filepath = backup_manager.backup_table("companies")

    # Backup completo
    summary = backup_manager.backup_all()

    # Relatorio resumido
    report = backup_manager.export_report()

    # Limpar backups antigos (>30 dias)
    backup_manager.cleanup_old_backups(days=30)
"""

import sys
import os
import csv
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger


# ============================================================================
# CONSTANTS
# ============================================================================

MAIN_TABLES: List[str] = [
    "companies",
    "contacts",
    "approval_queue",
    "interactions",
    "meetings",
    "api_usage",
    "follow_up_sequences",
]

MIN_BACKUPS_TO_KEEP: int = 3


# ============================================================================
# BACKUP MANAGER
# ============================================================================

class BackupManager:
    """
    Gerenciador de backups do Supabase para CSV local.

    Exporta dados de tabelas do Supabase para arquivos CSV,
    gera relatorios resumidos e gerencia ciclo de vida dos backups.

    Attributes:
        project_root (Path): Raiz do projeto para resolver caminhos.
    """

    def __init__(self) -> None:
        """Inicializa o BackupManager com o diretorio raiz do projeto."""
        self.project_root: Path = Path(__file__).parent.parent

    def _ensure_dir(self, output_dir: str) -> Path:
        """
        Garante que o diretorio de saida existe.

        Args:
            output_dir: Caminho relativo ao projeto para o diretorio.

        Returns:
            Path absoluto do diretorio criado/existente.
        """
        full_path: Path = self.project_root / output_dir
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path

    def backup_table(self, table_name: str, output_dir: str = "backups") -> str:
        """
        Exporta todos os dados de uma tabela para CSV.

        Args:
            table_name: Nome da tabela no Supabase.
            output_dir: Diretorio de saida (relativo ao projeto).

        Returns:
            Caminho completo do arquivo CSV gerado.

        Raises:
            Exception: Se falhar ao consultar ou salvar dados.
        """
        try:
            logger.info(
                f"Iniciando backup da tabela: {table_name}",
                extra={"table": table_name},
            )

            dir_path: Path = self._ensure_dir(output_dir)
            timestamp: str = datetime.now().strftime("%Y-%m-%d_%H%M")
            filename: str = f"{table_name}_{timestamp}.csv"
            filepath: Path = dir_path / filename

            # Query all data from table
            response = db.client.table(table_name).select("*").execute()
            rows: List[Dict[str, Any]] = response.data if response.data else []

            if not rows:
                logger.warning(
                    f"Tabela {table_name} vazia, criando CSV sem dados",
                    extra={"table": table_name},
                )
                filepath.touch()
                return str(filepath)

            # Write CSV
            headers: List[str] = list(rows[0].keys())
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)

            logger.info(
                f"Backup concluido: {table_name} ({len(rows)} registros)",
                extra={
                    "table": table_name,
                    "rows": len(rows),
                    "file": str(filepath),
                },
            )
            return str(filepath)

        except Exception as e:
            logger.error(
                f"Erro ao fazer backup de {table_name}: {e}",
                extra={"table": table_name, "error": str(e)},
            )
            raise

    def backup_all(self, output_dir: str = "backups") -> Dict[str, Any]:
        """
        Faz backup de todas as tabelas principais em uma subpasta com timestamp.

        Args:
            output_dir: Diretorio base de saida.

        Returns:
            Resumo do backup:
                - tables_backed_up (int): Quantidade de tabelas
                - total_rows (int): Total de linhas exportadas
                - folder (str): Caminho da pasta criada
                - details (List[Dict]): Detalhes por tabela
        """
        timestamp: str = datetime.now().strftime("%Y-%m-%d_%H%M")
        subfolder: str = f"{output_dir}/backup_{timestamp}"

        logger.info(
            f"Iniciando backup completo em: {subfolder}",
            extra={"folder": subfolder},
        )

        total_rows: int = 0
        details: List[Dict[str, Any]] = []
        tables_ok: int = 0

        for table_name in MAIN_TABLES:
            try:
                filepath: str = self.backup_table(table_name, subfolder)

                # Count rows in saved file
                row_count: int = 0
                saved_path: Path = Path(filepath)
                if saved_path.stat().st_size > 0:
                    with open(saved_path, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        row_count = max(0, sum(1 for _ in reader) - 1)  # minus header

                total_rows += row_count
                tables_ok += 1
                details.append({
                    "table": table_name,
                    "rows": row_count,
                    "file": filepath,
                    "status": "ok",
                })

            except Exception as e:
                logger.error(
                    f"Falha no backup de {table_name}: {e}",
                    extra={"table": table_name, "error": str(e)},
                )
                details.append({
                    "table": table_name,
                    "rows": 0,
                    "file": "",
                    "status": f"error: {e}",
                })

        summary: Dict[str, Any] = {
            "tables_backed_up": tables_ok,
            "total_rows": total_rows,
            "folder": str(self.project_root / subfolder),
            "details": details,
        }

        logger.info(
            f"Backup completo: {tables_ok}/{len(MAIN_TABLES)} tabelas, {total_rows} registros",
            extra=summary,
        )
        return summary

    def export_report(self, output_dir: str = "backups") -> str:
        """
        Gera CSV com relatorio resumido do sistema.

        Inclui: totais por status, contatos, metricas de email,
        top 10 escolas por score.

        Args:
            output_dir: Diretorio de saida.

        Returns:
            Caminho do arquivo de relatorio gerado.
        """
        try:
            dir_path: Path = self._ensure_dir(output_dir)
            date_str: str = datetime.now().strftime("%Y-%m-%d")
            filepath: Path = dir_path / f"relatorio_{date_str}.csv"

            report_rows: List[Dict[str, str]] = []

            # --- Schools by status ---
            try:
                response = db.client.table("companies").select("status").execute()
                companies: List[Dict] = response.data if response.data else []
                status_counts: Dict[str, int] = {}
                for c in companies:
                    s: str = c.get("status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1

                for status, count in sorted(status_counts.items()):
                    report_rows.append({
                        "categoria": "Escolas por Status",
                        "metrica": status,
                        "valor": str(count),
                    })
                report_rows.append({
                    "categoria": "Escolas por Status",
                    "metrica": "TOTAL",
                    "valor": str(len(companies)),
                })
            except Exception as e:
                logger.warning(f"Erro ao contar escolas: {e}")

            # --- Total contacts ---
            try:
                response = db.client.table("contacts").select("id", count="exact").execute()
                contact_count: int = response.count if response.count is not None else len(response.data or [])
                report_rows.append({
                    "categoria": "Contatos",
                    "metrica": "Total",
                    "valor": str(contact_count),
                })
            except Exception as e:
                logger.warning(f"Erro ao contar contatos: {e}")

            # --- Email metrics ---
            try:
                response = db.client.table("approval_queue").select("status").execute()
                queue_items: List[Dict] = response.data if response.data else []
                email_metrics: Dict[str, int] = {
                    "sent": 0,
                    "opened": 0,
                    "clicked": 0,
                    "replied": 0,
                }
                for item in queue_items:
                    s = item.get("status", "")
                    if s in email_metrics:
                        email_metrics[s] += 1
                    elif s == "approved":
                        email_metrics["sent"] += 1

                for metric, count in email_metrics.items():
                    report_rows.append({
                        "categoria": "Emails",
                        "metrica": metric,
                        "valor": str(count),
                    })
            except Exception as e:
                logger.warning(f"Erro ao contar emails: {e}")

            # --- Top 10 schools by score ---
            try:
                response = (
                    db.client.table("companies")
                    .select("name, qualification_score")
                    .not_.is_("qualification_score", "null")
                    .order("qualification_score", desc=True)
                    .limit(10)
                    .execute()
                )
                top_schools: List[Dict] = response.data if response.data else []
                for i, school in enumerate(top_schools, 1):
                    report_rows.append({
                        "categoria": "Top 10 Escolas",
                        "metrica": f"#{i} {school.get('name', 'N/A')}",
                        "valor": str(school.get("qualification_score", 0)),
                    })
            except Exception as e:
                logger.warning(f"Erro ao buscar top escolas: {e}")

            # --- Write report CSV ---
            if not report_rows:
                report_rows.append({
                    "categoria": "Info",
                    "metrica": "Status",
                    "valor": "Sem dados disponiveis",
                })

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["categoria", "metrica", "valor"]
                )
                writer.writeheader()
                writer.writerows(report_rows)

            logger.info(
                f"Relatorio exportado: {filepath}",
                extra={"file": str(filepath), "rows": len(report_rows)},
            )
            return str(filepath)

        except Exception as e:
            logger.error(f"Erro ao gerar relatorio: {e}", extra={"error": str(e)})
            raise

    def cleanup_old_backups(self, days: int = 30) -> None:
        """
        Remove backups mais antigos que X dias, mantendo ao menos os ultimos 3.

        Args:
            days: Idade maxima em dias para manter backups.
        """
        try:
            backups_dir: Path = self.project_root / "backups"
            if not backups_dir.exists():
                logger.info("Nenhum diretorio de backups encontrado")
                return

            cutoff: datetime = datetime.now() - timedelta(days=days)

            # List backup folders (backup_YYYY-MM-DD_HHmm)
            backup_folders: List[Path] = sorted(
                [
                    p
                    for p in backups_dir.iterdir()
                    if p.is_dir() and p.name.startswith("backup_")
                ],
                key=lambda p: p.stat().st_mtime,
            )

            if len(backup_folders) <= MIN_BACKUPS_TO_KEEP:
                logger.info(
                    f"Apenas {len(backup_folders)} backups encontrados, "
                    f"mantendo todos (minimo: {MIN_BACKUPS_TO_KEEP})"
                )
                return

            # Only consider removing older ones beyond the minimum to keep
            candidates: List[Path] = backup_folders[:-MIN_BACKUPS_TO_KEEP]
            removed: int = 0

            for folder in candidates:
                mod_time: datetime = datetime.fromtimestamp(folder.stat().st_mtime)
                if mod_time < cutoff:
                    shutil.rmtree(folder)
                    removed += 1
                    logger.info(
                        f"Backup removido: {folder.name}",
                        extra={"folder": str(folder)},
                    )

            logger.info(
                f"Limpeza concluida: {removed} backups removidos, "
                f"{len(backup_folders) - removed} mantidos"
            )

        except Exception as e:
            logger.error(f"Erro na limpeza de backups: {e}", extra={"error": str(e)})
            raise

    def get_backup_list(self) -> List[Dict[str, Any]]:
        """
        Lista backups existentes com data, tamanho e tabelas.

        Returns:
            Lista de dicts com info de cada backup:
                - name (str): Nome da pasta
                - date (str): Data formatada
                - size_mb (float): Tamanho total em MB
                - tables (List[str]): Tabelas incluidas
                - files (int): Quantidade de arquivos
        """
        try:
            backups_dir: Path = self.project_root / "backups"
            if not backups_dir.exists():
                return []

            result: List[Dict[str, Any]] = []

            backup_folders: List[Path] = sorted(
                [
                    p
                    for p in backups_dir.iterdir()
                    if p.is_dir() and p.name.startswith("backup_")
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for folder in backup_folders:
                csv_files: List[Path] = list(folder.glob("*.csv"))
                total_size: int = sum(f.stat().st_size for f in csv_files)
                tables: List[str] = [
                    f.stem.rsplit("_", 2)[0] for f in csv_files
                ]

                # Parse date from folder name (backup_YYYY-MM-DD_HHmm)
                date_str: str = folder.name.replace("backup_", "")
                try:
                    parsed_date: datetime = datetime.strptime(
                        date_str, "%Y-%m-%d_%H%M"
                    )
                    formatted_date: str = parsed_date.strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    formatted_date = date_str

                result.append({
                    "name": folder.name,
                    "date": formatted_date,
                    "size_mb": round(total_size / (1024 * 1024), 2),
                    "tables": tables,
                    "files": len(csv_files),
                })

            return result

        except Exception as e:
            logger.error(
                f"Erro ao listar backups: {e}", extra={"error": str(e)}
            )
            return []


# ============================================================================
# SINGLETON
# ============================================================================

backup_manager: BackupManager = BackupManager()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup Manager - IAprendo")
    parser.add_argument(
        "--action",
        choices=["table", "all", "report", "cleanup", "list"],
        default="all",
        help="Acao a executar (default: all)",
    )
    parser.add_argument("--table", type=str, help="Nome da tabela (para --action table)")
    parser.add_argument("--days", type=int, default=30, help="Dias para cleanup (default: 30)")

    args = parser.parse_args()

    if args.action == "table":
        if not args.table:
            print("Erro: --table obrigatorio para acao 'table'")
            sys.exit(1)
        path = backup_manager.backup_table(args.table)
        print(f"Backup salvo: {path}")

    elif args.action == "all":
        summary = backup_manager.backup_all()
        print(f"Backup completo: {summary['tables_backed_up']} tabelas, {summary['total_rows']} registros")
        print(f"Pasta: {summary['folder']}")

    elif args.action == "report":
        path = backup_manager.export_report()
        print(f"Relatorio salvo: {path}")

    elif args.action == "cleanup":
        backup_manager.cleanup_old_backups(days=args.days)
        print("Limpeza concluida")

    elif args.action == "list":
        backups = backup_manager.get_backup_list()
        if not backups:
            print("Nenhum backup encontrado")
        else:
            for b in backups:
                print(f"  {b['date']} | {b['size_mb']} MB | {b['files']} arquivos | {b['name']}")
