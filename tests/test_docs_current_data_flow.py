from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_flow_docs_reference_current_pipeline():
    text = (ROOT / "docs" / "数据流说明.md").read_text(encoding="utf-8")

    assert "backend/services/excel_pipeline.py" in text
    assert "backend/etl/" in text
    assert "backend/aggregator.py" not in text
