from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    default = Path(__file__).resolve().parents[1] / "market_analysis_data"
    return Path(os.getenv("MARKET_ANALYSIS_DATA_DIR", str(default))).expanduser().resolve()


SECTION_KEYS = ("macro", "regulation", "peers", "business_line")
CHANGE_KEYS = ("persistent", "strengthened", "reversed", "new", "expired")
REPORT_SCHEMA_VERSION = "1.0"
