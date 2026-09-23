"""Project assistant entry point; questions must contain public research topics only."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from market_analysis.hermes import discover, HermesError

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="", help="Public research topic; never supply internal data or secrets")
    args = parser.parse_args()
    try:
        print(json.dumps(discover(question=args.question), ensure_ascii=False))
    except HermesError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
