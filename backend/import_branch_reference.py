from __future__ import annotations

import argparse
from pathlib import Path

from branch_analysis.repository import import_reference_csv
from db import init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将证保网点参考表私密导入运行数据库")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--imported-by", default="server-cli")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    init_db()
    result = import_reference_csv(args.source, imported_by=args.imported_by)
    print(
        f"网点参考表导入成功：批次{result['batchId']}，"
        f"常规{result['regularCount']}个，转介绍{result['referralCount']}个"
    )


if __name__ == "__main__":
    main()
