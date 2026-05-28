import io
import zipfile

import pandas as pd

from backend.etl.columns import _read_excel


def test_read_excel_normalizes_backslash_zip_names():
    source = io.BytesIO()
    pd.DataFrame([{"业务模式": "OTO", "期交保费": 100}]).to_excel(source, index=False)

    malformed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source.getvalue()), "r") as zin:
        with zipfile.ZipFile(malformed, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                name = item.filename.replace("/", "\\")
                info = zipfile.ZipInfo(name, date_time=item.date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(info, zin.read(item.filename))

    df = _read_excel(malformed.getvalue(), {"业务模式", "期交保费"})

    assert df.to_dict("records") == [{"业务模式": "OTO", "期交保费": 100}]
