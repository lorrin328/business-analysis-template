import pandas as pd
import io
from typing import Dict, List

# 业务口径映射
CHANNEL_MAP = {'证券': '证保', '网服': '蚁桥'}


def parse_performance_excel(file_bytes: bytes) -> pd.DataFrame:
    """解析转型业务业绩Excel（OTO/证保/蚁桥）"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    # 列名标准化
    df.columns = [str(c).strip() for c in df.columns]
    # 映射渠道名称
    if '渠道' in df.columns:
        df['渠道'] = df['渠道'].replace(CHANNEL_MAP)
    elif '业务线' in df.columns:
        df['业务线'] = df['业务线'].replace(CHANNEL_MAP)
    return df


def parse_jingdai_excel(file_bytes: bytes) -> pd.DataFrame:
    """解析经代业务业绩Excel"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_hr_excel(file_bytes: bytes) -> pd.DataFrame:
    """解析人力基表Excel"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]
    # 映射渠道名称
    if '渠道' in df.columns:
        df['渠道'] = df['渠道'].replace(CHANNEL_MAP)
    elif '业务线' in df.columns:
        df['业务线'] = df['业务线'].replace(CHANNEL_MAP)
    return df


def parse_value_excel(file_bytes: bytes) -> pd.DataFrame:
    """解析价值基表Excel"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]
    if '渠道' in df.columns:
        df['渠道'] = df['渠道'].replace(CHANNEL_MAP)
    return df


def aggregate_performance(df: pd.DataFrame) -> Dict:
    """聚合转型业务业绩数据"""
    results = []

    # 自动识别列名
    year_col = next((c for c in df.columns if '年' in c), None)
    month_col = next((c for c in df.columns if '月' in c or '月份' in c), None)
    channel_col = next((c for c in df.columns if '渠道' in c or '业务线' in c or '系列' in c), None)
    qj_col = next((c for c in df.columns if '期交' in c), None)
    gm_col = next((c for c in df.columns if '规模' in c or '规保' in c), None)
    zs_col = next((c for c in df.columns if '折算' in c or '标准' in c), None)

    if not all([year_col, month_col, channel_col]):
        raise ValueError(f"无法识别必要列。当前列: {list(df.columns)}")

    grouped = df.groupby([year_col, month_col, channel_col])
    for (year, month, channel), group in grouped:
        qj = group[qj_col].sum() if qj_col else 0
        gm = group[gm_col].sum() if gm_col else 0
        zs = group[zs_col].sum() if zs_col else 0
        results.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'qj_premium': float(qj) if pd.notna(qj) else 0,
            'gm_premium': float(gm) if pd.notna(gm) else 0,
            'zs_premium': float(zs) if pd.notna(zs) else 0,
        })
    return results


def aggregate_jingdai(df: pd.DataFrame) -> Dict:
    """聚合经代业务业绩数据"""
    results = []

    year_col = next((c for c in df.columns if '年' in c), None)
    month_col = next((c for c in df.columns if '月' in c or '月份' in c), None)
    qj_col = next((c for c in df.columns if '期交' in c), None)
    gm_col = next((c for c in df.columns if '规模' in c or '规保' in c), None)
    zs_col = next((c for c in df.columns if '折算' in c or '标准' in c), None)

    if not all([year_col, month_col]):
        raise ValueError(f"无法识别必要列。当前列: {list(df.columns)}")

    grouped = df.groupby([year_col, month_col])
    for (year, month), group in grouped:
        qj = group[qj_col].sum() if qj_col else 0
        gm = group[gm_col].sum() if gm_col else 0
        zs = group[zs_col].sum() if zs_col else 0
        results.append({
            'year': int(year),
            'month': int(month),
            'qj_premium': float(qj) if pd.notna(qj) else 0,
            'gm_premium': float(gm) if pd.notna(gm) else 0,
            'zs_premium': float(zs) if pd.notna(zs) else 0,
        })
    return results


def aggregate_hr(df: pd.DataFrame) -> Dict:
    """聚合人力数据"""
    results = []

    year_col = next((c for c in df.columns if '年' in c), None)
    month_col = next((c for c in df.columns if '月' in c or '月份' in c), None)
    channel_col = next((c for c in df.columns if '渠道' in c or '业务线' in c or '系列' in c), None)
    start_col = next((c for c in df.columns if '月初' in c or '期初' in c or 'start' in c.lower()), None)
    end_col = next((c for c in df.columns if '月末' in c or '期末' in c or 'end' in c.lower()), None)
    active_col = next((c for c in df.columns if '活动' in c or '举绩' in c or 'active' in c.lower()), None)

    if not all([year_col, month_col, channel_col]):
        raise ValueError(f"无法识别人力数据必要列。当前列: {list(df.columns)}")

    grouped = df.groupby([year_col, month_col, channel_col])
    for (year, month, channel), group in grouped:
        start = group[start_col].sum() if start_col else 0
        end = group[end_col].sum() if end_col else 0
        active = group[active_col].sum() if active_col else 0
        results.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'start_headcount': int(start) if pd.notna(start) else 0,
            'end_headcount': int(end) if pd.notna(end) else 0,
            'active_headcount': int(active) if pd.notna(active) else 0,
        })
    return results


def aggregate_value(df: pd.DataFrame) -> Dict:
    """聚合价值数据"""
    results = []

    year_col = next((c for c in df.columns if '年' in c), None)
    month_col = next((c for c in df.columns if '月' in c or '月份' in c), None)
    channel_col = next((c for c in df.columns if '渠道' in c or '业务线' in c or '系列' in c), None)
    value_col = next((c for c in df.columns if '价值' in c), None)

    if not all([year_col, month_col, channel_col]):
        raise ValueError(f"无法识别价值数据必要列。当前列: {list(df.columns)}")

    grouped = df.groupby([year_col, month_col, channel_col])
    for (year, month, channel), group in grouped:
        val = group[value_col].sum() if value_col else 0
        results.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'value_premium': float(val) if pd.notna(val) else 0,
        })
    return results
