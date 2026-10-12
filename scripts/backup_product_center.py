"""Local recovery-set CLI. Restore always targets a new/empty directory."""
from pathlib import Path
import argparse
import json
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from product_center.backup import create_backup, restore_backup, verify_backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','verify','restore'])
    parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--data-root',type=Path)
    parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    try:
        if args.action=='create':
            if not args.database or not args.data_root:
                parser.error('create requires --database and --data-root')
            # The import lock module reads the database location at import time.
            os.environ['BUSINESS_ANALYSIS_DB']=str(args.database.resolve())
            from services.operation_lock import operation_lock
            with operation_lock('product-center-backup',timeout=1):
                result=create_backup(args.database,args.data_root,args.archive)
        elif args.action=='restore':
            if not args.destination:
                parser.error('restore requires --destination')
            result=restore_backup(args.archive,args.destination)
        else:
            result=verify_backup(args.archive)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print('Recovery-set validation failed: '+type(exc).__name__,file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
