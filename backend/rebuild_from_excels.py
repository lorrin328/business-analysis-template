from pathlib import Path

from db import get_db, init_db
from services.excel_pipeline import (
    ExcelSource,
    build_excel_pipeline_result,
    clear_pipeline_years,
    write_excel_pipeline_result,
)
from services.operation_lock import operation_lock
from services.product_config_service import purge_non_jingdai_product_config


ROOT = Path(__file__).resolve().parent.parent

EXCEL_SOURCE_PATTERNS = {
    'performance': 'AI-\u7ecf\u8425\u5206\u6790\u4e1a\u7ee9\u57fa\u8868*.xlsx',
    'value': 'AI-\u7ecf\u8425\u5206\u6790\u4ef7\u503c\u57fa\u8868*.xlsx',
    'hr': 'N1AI-\u4eba\u529b\u57fa\u8868*.xlsx',
    'jingdai': '*\u7ecf\u4ee3*\u4e1a\u7ee9*.xlsx',
}


def _pick(pattern: str) -> Path | None:
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def find_excel_sources(required: bool = True) -> dict[str, Path | None]:
    sources = {name: _pick(pattern) for name, pattern in EXCEL_SOURCE_PATTERNS.items()}
    if required:
        missing = [name for name, path in sources.items() if path is None]
        if missing:
            existing = ', '.join(sorted(p.name for p in ROOT.glob('*.xlsx'))) or 'none'
            raise FileNotFoundError(
                f"Missing required Excel source(s): {', '.join(missing)}. "
                f"Existing root Excel files: {existing}"
            )
    return sources


def main():
    with operation_lock("excel-rebuild", timeout=1.0):
        _main_locked()


def _main_locked():
    init_db()
    with get_db() as conn:
        purged = purge_non_jingdai_product_config(conn)
        conn.commit()
        if purged:
            print(f'product_config: purged {purged} non-jingdai rows')

    sources = find_excel_sources(required=True)
    performance_file = sources['performance']
    value_file = sources['value']
    hr_file = sources['hr']
    jingdai_file = sources['jingdai']

    result = build_excel_pipeline_result([
        ExcelSource("performance", performance_file.name, performance_file.read_bytes()),
        ExcelSource("jingdai", jingdai_file.name, jingdai_file.read_bytes()),
        ExcelSource("hr", hr_file.name, hr_file.read_bytes()),
        ExcelSource("value", value_file.name, value_file.read_bytes()),
    ])
    for summary in result.source_summaries:
        print(summary)
    if result.cutoff_warnings:
        for warning in result.cutoff_warnings:
            print(f'warning: {warning}')

    with get_db() as conn:
        clear_pipeline_years(conn, result.data_years)
        write_excel_pipeline_result(conn, result, incremental=False)
        conn.commit()

    print(f'loaded years: {result.data_years}')


if __name__ == '__main__':
    main()
