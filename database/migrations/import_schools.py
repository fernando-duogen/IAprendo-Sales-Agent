"""
CSV Import Migration - Importa escolas do CSV do MEC com filtros ICP.

Este script importa até 210.000 escolas do CSV oficial do MEC, aplicando
4 filtros ICP (Ideal Customer Profile) para selecionar apenas leads qualificados.

Filtros Aplicados:
    1. Restrição: "FUNCIONAMENTO E SEM RESTRIÇÃO"
    2. Localização: TARGET_CITY + TARGET_STATE
    3. Níveis de Ensino: Fundamental OU Médio
    4. Tipo de Escola: TARGET_SCHOOL_TYPES (configurável)

Features:
    - Batch processing (500 por vez) para performance
    - Detecção automática de duplicatas por código INEP
    - Validação robusta de dados (coordenadas, estado, campos obrigatórios)
    - Modo --sample N para testar com subset
    - Modo --skip-validation para debug rápido

Usage:
    # Teste com 100 escolas
    python database/migrations/002_import_schools.py --sample 100

    # Importação completa
    python database/migrations/002_import_schools.py

    # Sem validação (debug)
    python database/migrations/002_import_schools.py --sample 50 --skip-validation

Resultado:
    - Escolas inseridas na tabela 'companies' com status='raw'
    - Relatório detalhado com funil de filtros
    - Logs estruturados em logs/application.log

Exit Codes:
    0 - Sucesso (pelo menos 1 escola importada)
    1 - Falha (erro de validação, CSV inválido, banco offline)
"""

import sys
import argparse
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd

# Adiciona o diretório raiz ao path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from database.supabase_client import db, DatabaseError
from utils.logger import logger


# ============================================================================
# CONSTANTES
# ============================================================================

BATCH_SIZE = 500  # Escolas por batch


# ============================================================================
# ARGUMENTOS CLI
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parseia argumentos da linha de comando.

    Returns:
        Namespace com argumentos parseados.

    Example:
        >>> args = parse_arguments()
        >>> print(args.sample)
        100
    """
    parser = argparse.ArgumentParser(
        description="Importa escolas do CSV do MEC para o banco Supabase"
    )

    parser.add_argument(
        '--sample',
        type=int,
        default=None,
        help='Importar apenas N escolas (para teste). Ex: --sample 100'
    )

    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Pular validações de dados (apenas para debug)'
    )

    args = parser.parse_args()

    logger.info(
        "Argumentos parseados",
        extra={
            'sample_size': args.sample,
            'skip_validation': args.skip_validation
        }
    )

    return args


# ============================================================================
# VALIDAÇÃO DE PRÉ-REQUISITOS
# ============================================================================

def validate_prerequisites() -> bool:
    """
    Valida pré-requisitos antes de importar CSV.

    Verifica:
        - CSV existe (settings.CSV_PATH)
        - Tabela companies existe (migration 001 executada)
        - Settings ICP obrigatórias (TARGET_CITY, TARGET_STATE)

    Returns:
        True se todos os pré-requisitos estão OK.

    Raises:
        ValueError: Se algum pré-requisito falhar.

    Example:
        >>> validate_prerequisites()
        True
    """
    logger.info("Validando pré-requisitos", extra={'step': 'validation'})

    # 1. Validar CSV existe
    csv_path = Path(settings.CSV_PATH)

    if not csv_path.exists():
        raise ValueError(
            f"CSV não encontrado: {settings.CSV_PATH}\n\n"
            f"Por favor:\n"
            f"  1. Baixe o CSV oficial do MEC\n"
            f"  2. Coloque em: {csv_path.parent}\n"
            f"  3. Ou ajuste CSV_PATH no .env"
        )

    if not csv_path.is_file():
        raise ValueError(f"{settings.CSV_PATH} não é um arquivo válido")

    # 2. Validar tabela companies existe
    try:
        db.client.table('companies').select('id').limit(1).execute()
    except Exception as e:
        raise ValueError(
            "Tabela 'companies' não encontrada.\n\n"
            "Execute a migration 001 primeiro:\n"
            "  python database/migrations/001_setup_database.py"
        ) from e

    # 3. Validar configurações ICP
    if not settings.TARGET_CITY:
        raise ValueError("TARGET_CITY não configurada no .env")

    if not settings.TARGET_STATE:
        raise ValueError("TARGET_STATE não configurada no .env")

    if not settings.TARGET_SCHOOL_TYPES:
        raise ValueError("TARGET_SCHOOL_TYPES não configurada no .env")

    logger.info(
        "Pré-requisitos validados",
        extra={
            'csv_exists': True,
            'csv_size_mb': round(csv_path.stat().st_size / 1024 / 1024, 2),
            'table_companies_exists': True,
            'target_city': settings.TARGET_CITY,
            'target_state': settings.TARGET_STATE
        }
    )

    return True


# ============================================================================
# CARREGAMENTO DO CSV
# ============================================================================

def load_csv(sample_size: Optional[int] = None) -> pd.DataFrame:
    """
    Carrega CSV de escolas do MEC.

    Args:
        sample_size: Se fornecido, carrega apenas N primeiras linhas.

    Returns:
        DataFrame do pandas com dados do CSV.

    Raises:
        ValueError: Se CSV estiver vazio ou inválido.
        IOError: Se houver erro ao ler CSV.

    Example:
        >>> df = load_csv(sample_size=100)
        >>> print(len(df))
        100
    """
    csv_path = Path(settings.CSV_PATH)

    logger.info(
        "Carregando CSV",
        extra={
            'file_path': str(csv_path),
            'sample_size': sample_size,
            'encoding': settings.CSV_ENCODING,
            'step': 'loading'
        }
    )

    try:
        # Carregar CSV
        read_kwargs = {
            'encoding': settings.CSV_ENCODING,
            'low_memory': False  # Evita warning com tipos mistos
        }

        if sample_size:
            read_kwargs['nrows'] = sample_size

        df = pd.read_csv(csv_path, **read_kwargs)

        # Validar que não está vazio
        if len(df) == 0:
            raise ValueError("CSV está vazio")

        # Validar colunas obrigatórias
        col_map = settings.get_csv_column_mapping()
        required_cols = ['name', 'inep_code', 'city', 'state', 'restriction', 'education_levels']

        for col_key in required_cols:
            col_name = col_map.get(col_key)
            if col_name not in df.columns:
                raise ValueError(
                    f"Coluna obrigatória '{col_name}' não encontrada no CSV.\n"
                    f"Colunas disponíveis: {', '.join(df.columns[:10])}..."
                )

        logger.info(
            "CSV carregado",
            extra={
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'sample_mode': sample_size is not None
            }
        )

        return df

    except pd.errors.EmptyDataError:
        raise ValueError("CSV está vazio ou corrompido")

    except pd.errors.ParserError as e:
        raise ValueError(f"Erro ao parsear CSV: {e}")

    except Exception as e:
        logger.error(
            "Erro ao carregar CSV",
            extra={
                'file_path': str(csv_path),
                'error': str(e)
            },
            exc_info=True
        )
        raise IOError(f"Falha ao carregar CSV: {e}") from e


# ============================================================================
# FILTROS ICP
# ============================================================================

def apply_filters(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Aplica 4 filtros ICP (Ideal Customer Profile) no DataFrame.

    Filtros:
        1. Restrição: "FUNCIONAMENTO E SEM RESTRIÇÃO"
        2. Localização: TARGET_CITY + TARGET_STATE
        3. Níveis: Fundamental OU Médio
        4. Tipo: TARGET_SCHOOL_TYPES (pública, privada, etc)

    Args:
        df: DataFrame com dados brutos do CSV.

    Returns:
        Tupla (df_filtered, stats) onde:
            - df_filtered: DataFrame filtrado
            - stats: Dict com contadores de cada etapa

    Example:
        >>> df_filtered, stats = apply_filters(df)
        >>> print(stats['filter_4_approved'])
        1500
    """
    col_map = settings.get_csv_column_mapping()

    logger.info(
        "Aplicando filtros ICP",
        extra={
            'initial_count': len(df),
            'step': 'filtering'
        }
    )

    stats = {
        'initial': len(df),
        'filter_1_restriction': 0,
        'filter_2_location': 0,
        'filter_3_levels': 0,
        'filter_4_approved': 0
    }

    # FILTRO 1: Restrição de Atendimento
    logger.debug("Aplicando Filtro 1: Restrição de Atendimento")

    df = df[
        df[col_map['restriction']].str.contains(
            "FUNCIONAMENTO E SEM RESTRIÇÃO",
            case=False,
            na=False
        )
    ]

    stats['filter_1_restriction'] = len(df)

    logger.debug(
        "Filtro 1 aplicado",
        extra={
            'remaining': len(df),
            'removed': stats['initial'] - len(df)
        }
    )

    # FILTRO 2: Localização (Cidade + Estado)
    # Suporta multiplas cidades/estados separados por virgula
    # Se TARGET_CITY ou TARGET_STATE for vazio, o filtro e ignorado (Brasil todo)
    logger.debug("Aplicando Filtro 2: Localização")

    before_filter2 = len(df)
    target_city_raw = settings.TARGET_CITY.strip()
    target_state_raw = settings.TARGET_STATE.strip()

    if target_city_raw:
        target_cities = [c.strip().upper() for c in target_city_raw.split(",") if c.strip()]
        df = df[df[col_map['city']].str.upper().isin(target_cities)]

    if target_state_raw:
        target_states = [s.strip().upper() for s in target_state_raw.split(",") if s.strip()]
        df = df[df[col_map['state']].str.upper().isin(target_states)]

    stats['filter_2_location'] = len(df)

    logger.debug(
        "Filtro 2 aplicado",
        extra={
            'remaining': len(df),
            'removed': before_filter2 - len(df),
            'target_city': target_city_raw or "(todos)",
            'target_state': target_state_raw or "(todos)"
        }
    )

    # FILTRO 3: Níveis de Ensino (Fundamental OU Médio)
    logger.debug("Aplicando Filtro 3: Níveis de Ensino")

    def has_target_level(education_levels_str: Any) -> bool:
        """Verifica se contém fundamental ou médio."""
        if pd.isna(education_levels_str):
            return False

        text = str(education_levels_str).lower()

        # Buscar por qualquer nível alvo
        for level in settings.TARGET_EDUCATION_LEVELS:
            if level.lower() in text:
                return True

        return False

    df = df[df[col_map['education_levels']].apply(has_target_level)]

    stats['filter_3_levels'] = len(df)

    logger.debug(
        "Filtro 3 aplicado",
        extra={
            'remaining': len(df),
            'target_levels': settings.TARGET_EDUCATION_LEVELS
        }
    )

    # FILTRO 4: Tipo de Escola (Pública, Privada, etc)
    logger.debug("Aplicando Filtro 4: Tipo de Escola")

    def matches_school_type(admin_dependency_str: Any) -> bool:
        """Verifica se corresponde ao tipo alvo."""
        if pd.isna(admin_dependency_str):
            return False

        text = str(admin_dependency_str).lower()

        # Buscar por qualquer tipo alvo
        for school_type in settings.TARGET_SCHOOL_TYPES:
            if school_type.lower() in text:
                return True

        return False

    df = df[df[col_map['admin_dependency']].apply(matches_school_type)]

    stats['filter_4_approved'] = len(df)

    logger.debug(
        "Filtro 4 aplicado",
        extra={
            'remaining': len(df),
            'target_types': settings.TARGET_SCHOOL_TYPES
        }
    )

    # Resumo
    approval_rate = (stats['filter_4_approved'] / stats['initial'] * 100) if stats['initial'] > 0 else 0

    logger.info(
        "Filtros ICP aplicados",
        extra={
            'initial': stats['initial'],
            'approved': stats['filter_4_approved'],
            'approval_rate_pct': round(approval_rate, 2)
        }
    )

    return df, stats


# ============================================================================
# VALIDAÇÃO DE DADOS
# ============================================================================

def validate_row(
    row: pd.Series,
    col_map: Dict[str, str],
    skip_validation: bool
) -> Tuple[bool, str]:
    """
    Valida uma linha do CSV.

    Validações:
        - Campos obrigatórios: name, inep_code
        - Latitude válida: -33 a 5 (Brasil)
        - Longitude válida: -74 a -34 (Brasil)
        - Estado: 2 letras

    Args:
        row: Linha do DataFrame (pd.Series).
        col_map: Mapeamento de colunas.
        skip_validation: Se True, pula validações.

    Returns:
        Tupla (is_valid, error_message).

    Example:
        >>> is_valid, error = validate_row(row, col_map, False)
        >>> if not is_valid:
        >>>     print(f"Linha inválida: {error}")
    """
    # Campos obrigatórios
    name = row.get(col_map['name'])
    inep_code = row.get(col_map['inep_code'])

    if pd.isna(name) or str(name).strip() == '':
        return False, "Nome vazio"

    if pd.isna(inep_code) or str(inep_code).strip() == '':
        return False, "Código INEP vazio"

    # Se skip_validation, parar aqui
    if skip_validation:
        return True, ""

    # Validar coordenadas (se presentes)
    lat = row.get(col_map.get('latitude'))
    lng = row.get(col_map.get('longitude'))

    # Limpar strings com espaços antes de validar
    if isinstance(lat, str):
        lat = lat.strip() or None
    if isinstance(lng, str):
        lng = lng.strip() or None

    if pd.notna(lat) and lat is not None and pd.notna(lng) and lng is not None:
        try:
            lat_float = float(str(lat).strip())
            lng_float = float(str(lng).strip())

            # Limites do Brasil
            if not (-33 <= lat_float <= 5):
                return False, f"Latitude inválida: {lat_float}"

            if not (-74 <= lng_float <= -34):
                return False, f"Longitude inválida: {lng_float}"

        except (ValueError, TypeError):
            return False, "Coordenadas não numéricas"

    # Validar estado
    state = row.get(col_map.get('state'))
    if pd.notna(state):
        state_str = str(state).strip()
        if len(state_str) != 2:
            return False, f"Estado inválido: {state}"

    return True, ""


# ============================================================================
# CONVERSÃO DE DADOS
# ============================================================================

def row_to_company_dict(row: pd.Series, col_map: Dict[str, str]) -> Dict[str, Any]:
    """
    Converte linha do CSV para dicionário de company.

    Args:
        row: Linha do DataFrame.
        col_map: Mapeamento de colunas.

    Returns:
        Dict pronto para db.insert_company().

    Example:
        >>> company_data = row_to_company_dict(row, col_map)
        >>> print(company_data['name'])
        'Escola Exemplo'
    """
    # Função auxiliar para obter valor ou None
    def get_value(col_key: str) -> Optional[Any]:
        col_name = col_map.get(col_key)
        if not col_name:
            return None

        value = row.get(col_name)
        if pd.isna(value):
            return None

        # Converter string vazia para None
        if isinstance(value, str) and value.strip() == '':
            return None

        return value

    # Converter latitude/longitude para float
    def get_coordinate(col_key: str) -> Optional[float]:
        value = get_value(col_key)
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    # Montar dicionário
    company_data = {
        # Obrigatórios
        'name': str(get_value('name')).strip(),
        'inep_code': str(get_value('inep_code')).strip(),

        # Localização
        'city': get_value('city'),
        'state': get_value('state'),
        'address': get_value('address'),
        'latitude': get_coordinate('latitude'),
        'longitude': get_coordinate('longitude'),

        # Classificação
        'admin_category': get_value('admin_category'),
        'admin_dependency': get_value('admin_dependency'),
        'education_levels': get_value('education_levels'),
        'school_size': get_value('size'),

        # Contato
        'phone': get_value('phone'),

        # Status inicial
        'status': 'raw',
        'source': 'csv_import'
    }

    return company_data


# ============================================================================
# PROCESSAMENTO EM BATCHES
# ============================================================================

def process_batch(
    batch: pd.DataFrame,
    col_map: Dict[str, str],
    skip_validation: bool,
    batch_num: int,
    total_batches: int
) -> Dict[str, int]:
    """
    Processa um batch de escolas.

    Args:
        batch: DataFrame com subset de escolas.
        col_map: Mapeamento de colunas.
        skip_validation: Se True, pula validações.
        batch_num: Número do batch atual.
        total_batches: Total de batches.

    Returns:
        Dict com estatísticas: {
            'processed': int,
            'inserted': int,
            'duplicates': int,
            'invalid': int,
            'errors': int
        }

    Example:
        >>> stats = process_batch(batch, col_map, False, 1, 10)
        >>> print(f"Inseridas: {stats['inserted']}")
    """
    logger.debug(
        f"Processando batch {batch_num}/{total_batches}",
        extra={
            'batch_number': batch_num,
            'batch_size': len(batch)
        }
    )

    stats = {
        'processed': 0,
        'inserted': 0,
        'duplicates': 0,
        'invalid': 0,
        'errors': 0
    }

    for idx, row in batch.iterrows():
        stats['processed'] += 1

        try:
            # 1. Validar
            is_valid, error_msg = validate_row(row, col_map, skip_validation)

            if not is_valid:
                stats['invalid'] += 1
                logger.debug(
                    f"Linha inválida (batch {batch_num})",
                    extra={
                        'batch_number': batch_num,
                        'row_index': idx,
                        'error': error_msg
                    }
                )
                continue

            # 2. Converter para dict
            company_data = row_to_company_dict(row, col_map)
            inep_code = company_data['inep_code']

            # 3. Verificar duplicata (CRÍTICO - Regra #5)
            existing = db.get_company_by_inep(inep_code)

            if existing:
                stats['duplicates'] += 1
                logger.debug(
                    f"Duplicata detectada (INEP: {inep_code})",
                    extra={
                        'inep_code': inep_code,
                        'existing_id': existing['id'],
                        'batch_number': batch_num
                    }
                )
                continue

            # 4. Inserir
            company_id = db.insert_company(company_data)

            if company_id:
                stats['inserted'] += 1
            else:
                stats['errors'] += 1
                logger.warning(
                    f"Falha ao inserir (sem erro explícito)",
                    extra={
                        'inep_code': inep_code,
                        'batch_number': batch_num
                    }
                )

        except DatabaseError as e:
            stats['errors'] += 1
            logger.error(
                f"Erro de banco ao processar linha (batch {batch_num})",
                extra={
                    'batch_number': batch_num,
                    'row_index': idx,
                    'error': str(e)
                }
            )

        except Exception as e:
            stats['errors'] += 1
            logger.error(
                f"Erro inesperado ao processar linha (batch {batch_num})",
                extra={
                    'batch_number': batch_num,
                    'row_index': idx,
                    'error': str(e)
                },
                exc_info=True
            )

    logger.debug(
        f"Batch {batch_num}/{total_batches} concluído",
        extra={
            'batch_number': batch_num,
            'inserted': stats['inserted'],
            'duplicates': stats['duplicates'],
            'invalid': stats['invalid'],
            'errors': stats['errors']
        }
    )

    return stats


def import_schools(
    df_filtered: pd.DataFrame,
    skip_validation: bool
) -> Dict[str, int]:
    """
    Importa escolas filtradas em batches.

    Args:
        df_filtered: DataFrame com escolas filtradas.
        skip_validation: Se True, pula validações.

    Returns:
        Dict com estatísticas totais.

    Raises:
        DatabaseError: Se erro crítico no banco.

    Example:
        >>> stats = import_schools(df_filtered, skip_validation=False)
        >>> print(f"Total inserido: {stats['inserted']}")
    """
    col_map = settings.get_csv_column_mapping()
    total_schools = len(df_filtered)
    total_batches = (total_schools // BATCH_SIZE) + 1

    logger.info(
        "Iniciando importação em batches",
        extra={
            'total_schools': total_schools,
            'batch_size': BATCH_SIZE,
            'total_batches': total_batches,
            'skip_validation': skip_validation,
            'step': 'importing'
        }
    )

    # Estatísticas acumuladas
    totals = {
        'processed': 0,
        'inserted': 0,
        'duplicates': 0,
        'invalid': 0,
        'errors': 0
    }

    print(f"\n📥 Importando {total_schools} escolas em {total_batches} batches de {BATCH_SIZE}...\n")

    # Processar em batches
    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * BATCH_SIZE
        end_idx = start_idx + BATCH_SIZE
        batch = df_filtered.iloc[start_idx:end_idx]

        if len(batch) == 0:
            break

        # Processar batch
        batch_stats = process_batch(batch, col_map, skip_validation, batch_num, total_batches)

        # Acumular
        for key in totals:
            totals[key] += batch_stats[key]

        # Progresso em tempo real
        progress_pct = round((totals['processed'] / total_schools) * 100, 1)
        print(
            f"  Batch {batch_num}/{total_batches}: "
            f"{progress_pct}% ({totals['processed']}/{total_schools}) | "
            f"✓ {totals['inserted']} inseridas | "
            f"⊗ {totals['duplicates']} duplicatas | "
            f"✗ {totals['invalid']} inválidas | "
            f"⚠ {totals['errors']} erros"
        )

    print()  # Linha em branco

    logger.info(
        "Importação concluída",
        extra={
            'total_processed': totals['processed'],
            'total_inserted': totals['inserted'],
            'total_duplicates': totals['duplicates'],
            'total_invalid': totals['invalid'],
            'total_errors': totals['errors']
        }
    )

    return totals


# ============================================================================
# RELATÓRIO FINAL
# ============================================================================

def generate_report(
    filter_stats: Dict[str, int],
    import_stats: Dict[str, int],
    sample_size: Optional[int],
    duration_seconds: float
) -> str:
    """
    Gera relatório formatado da importação.

    Args:
        filter_stats: Estatísticas dos filtros.
        import_stats: Estatísticas da importação.
        sample_size: Se foi modo sample.
        duration_seconds: Tempo total de execução.

    Returns:
        String com relatório formatado.

    Example:
        >>> report = generate_report(filter_stats, import_stats, None, 142.3)
        >>> print(report)
    """
    # Calcular taxa de aprovação
    approval_rate = 0.0
    if filter_stats['initial'] > 0:
        approval_rate = (filter_stats['filter_4_approved'] / filter_stats['initial']) * 100

    # Calcular taxa de sucesso
    success_rate = 0.0
    if import_stats['processed'] > 0:
        success_rate = (import_stats['inserted'] / import_stats['processed']) * 100

    report = f"""
{'='*70}
  CSV IMPORT MIGRATION - RELATÓRIO FINAL
{'='*70}

🚀 MODO: {"Importação de amostra (" + str(sample_size) + " linhas)" if sample_size else "Importação completa"}

🔍 FILTROS APLICADOS:
  Total inicial no CSV: {filter_stats['initial']:,}
  ↓ Filtro 1 (Restrição): {filter_stats['filter_1_restriction']:,}
  ↓ Filtro 2 (Localização): {filter_stats['filter_2_location']:,}
  ↓ Filtro 3 (Níveis): {filter_stats['filter_3_levels']:,}
  ↓ Filtro 4 (Tipo): {filter_stats['filter_4_approved']:,}
  ✓ Total aprovado: {filter_stats['filter_4_approved']:,}
  Taxa de aprovação: {approval_rate:.2f}%

📥 IMPORTAÇÃO:
  Escolas processadas: {import_stats['processed']:,}
  ✓ Inseridas: {import_stats['inserted']:,}
  ⊗ Duplicatas: {import_stats['duplicates']:,}
  ✗ Inválidas: {import_stats['invalid']:,}
  ⚠  Erros: {import_stats['errors']:,}
  Taxa de sucesso: {success_rate:.2f}%

📊 RESUMO:
  {import_stats['inserted']:,} escolas adicionadas ao banco
  Status: raw
  Tabela: companies

🎯 PRÓXIMOS PASSOS:
  1. Verificar dados: streamlit run dashboard/app.py
  2. Qualificar escolas: python workflows/daily_pipeline.py
"""

    # Adicionar features opcionais (se disponíveis)
    if settings.ENABLE_GEOCODING and settings.GOOGLE_MAPS_API_KEY:
        report += "  3. (Opcional) Geocodificar: python -m tools.geocoder\n"

    if settings.ENABLE_PHONE_SEARCH:
        report += "  4. (Opcional) Buscar telefones: python -m tools.phone_finder\n"

    report += f"""
{'='*70}

⏱️  Tempo total: {duration_seconds:.1f} segundos
"""

    return report


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """
    Função principal da migração.

    Orquestra:
        1. Parse de argumentos
        2. Validação de pré-requisitos
        3. Carregamento do CSV
        4. Aplicação dos filtros ICP
        5. Importação em batches
        6. Geração do relatório

    Returns:
        Exit code (0 = sucesso, 1 = falha).

    Example:
        >>> exit_code = main()
        >>> sys.exit(exit_code)
    """
    start_time = time.time()

    print("\n" + "="*70)
    print("  CSV IMPORT MIGRATION - 002")
    print("="*70 + "\n")

    try:
        # 1. Argumentos
        args = parse_arguments()

        if args.sample:
            print(f"🧪 MODO TESTE: Importando apenas {args.sample} escolas\n")

        if args.skip_validation:
            print("⚠️  AVISO: Validação de dados desabilitada\n")

        # 2. Validar pré-requisitos
        print("📋 Validando pré-requisitos...")
        validate_prerequisites()
        print("   ✓ Pré-requisitos OK\n")

        # 3. Carregar CSV
        print("📄 Carregando CSV...")
        df = load_csv(sample_size=args.sample)
        print(f"   ✓ {len(df):,} escolas carregadas\n")

        # 4. Aplicar filtros ICP
        print("🔍 Aplicando filtros ICP...")
        df_filtered, filter_stats = apply_filters(df)
        print(f"   ✓ {len(df_filtered):,} escolas aprovadas nos filtros\n")

        # Verificar se há escolas para importar
        if len(df_filtered) == 0:
            print("⚠️  AVISO: Nenhuma escola aprovada nos filtros!")
            print("\nVerifique as configurações ICP no .env:")
            print(f"  - TARGET_CITY: {settings.TARGET_CITY}")
            print(f"  - TARGET_STATE: {settings.TARGET_STATE}")
            print(f"  - TARGET_SCHOOL_TYPES: {settings.TARGET_SCHOOL_TYPES}")
            print(f"  - TARGET_EDUCATION_LEVELS: {settings.TARGET_EDUCATION_LEVELS}")
            print()
            return 1

        # 5. Importar escolas
        import_stats = import_schools(df_filtered, skip_validation=args.skip_validation)

        # 6. Gerar relatório
        duration = time.time() - start_time
        report = generate_report(filter_stats, import_stats, args.sample, duration)
        print(report)

        # Log final
        logger.info(
            "Migração 002 concluída",
            extra={
                'success': True,
                'schools_inserted': import_stats['inserted'],
                'duration_seconds': round(duration, 1)
            }
        )

        # Retornar sucesso se pelo menos 1 escola foi inserida
        if import_stats['inserted'] > 0:
            return 0
        else:
            print("❌ Nenhuma escola foi inserida. Verifique os logs.\n")
            return 1

    except ValueError as e:
        print(f"\n❌ ERRO DE VALIDAÇÃO: {e}\n")
        logger.error(f"Validação falhou: {e}")
        return 1

    except DatabaseError as e:
        print(f"\n❌ ERRO DE BANCO: {e}\n")
        logger.error(f"Erro de banco: {e}", exc_info=True)
        return 1

    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}\n")
        logger.critical(f"Erro inesperado: {e}", exc_info=True)
        return 1


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
