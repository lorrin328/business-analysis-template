import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_rebuild_from_excels_picks_required_unicode_sources(tmp_path, monkeypatch):
    import rebuild_from_excels

    filenames = {
        "performance": "AI-\u7ecf\u8425\u5206\u6790\u4e1a\u7ee9\u57fa\u8868_20260528.xlsx",
        "value": "AI-\u7ecf\u8425\u5206\u6790\u4ef7\u503c\u57fa\u8868_20260528.xlsx",
        "hr": "N1AI-\u4eba\u529b\u57fa\u8868_20260528.xlsx",
        "jingdai": "\u7ecf\u4ee3\u4e1a\u7ee9\u5206\u6790.xlsx",
    }
    for filename in filenames.values():
        (tmp_path / filename).write_bytes(b"placeholder")

    monkeypatch.setattr(rebuild_from_excels, "ROOT", tmp_path)

    sources = rebuild_from_excels.find_excel_sources(required=True)

    assert {key: path.name for key, path in sources.items()} == filenames


def test_rebuild_from_excels_fails_when_required_source_missing(tmp_path, monkeypatch):
    import pytest
    import rebuild_from_excels

    (tmp_path / "AI-\u7ecf\u8425\u5206\u6790\u4e1a\u7ee9\u57fa\u8868_20260528.xlsx").write_bytes(b"placeholder")
    monkeypatch.setattr(rebuild_from_excels, "ROOT", tmp_path)

    with pytest.raises(FileNotFoundError) as exc:
        rebuild_from_excels.find_excel_sources(required=True)

    message = str(exc.value)
    assert "Missing required Excel source(s)" in message
    assert "value" in message
    assert "hr" in message
    assert "jingdai" in message


def test_rebuild_from_excels_also_reads_daily_import_folder(tmp_path, monkeypatch):
    import rebuild_from_excels

    source_dir = tmp_path / "excel" / "原每日导入"
    source_dir.mkdir(parents=True)
    filenames = {
        "performance": "AI-经营分析业绩基表_20260826.xlsx",
        "value": "AI-经营分析价值基表_20260826.xlsx",
        "hr": "N1AI-人力基表_20260826.xlsx",
        "jingdai": "经代业绩分析.xlsx",
    }
    for filename in filenames.values():
        (source_dir / filename).write_bytes(b"placeholder")

    monkeypatch.setattr(rebuild_from_excels, "ROOT", tmp_path)
    sources = rebuild_from_excels.find_excel_sources(required=True)

    assert {key: path.name for key, path in sources.items()} == filenames
