"""One source contract for old stored data and new policy detail."""
import pandas as pd
import pytest

from etl.jingdai_contract import normalize_jingdai_source


def identity(**changes):
    values = {'时间': '2026-01-01', '经代机构': '平台', '产品名称': '产品',
              '投保单号': '000001', '缴费年限': '5', '缴别': '月交',
              '期交保费': 10, '承保年化规保': 10, '长短险': '长险'}
    values.update(changes)
    return values


def test_daily_contributions_keep_range_identity_non_additive():
    source = pd.DataFrame([identity(), identity(期交保费=-10),
        identity(时间='2026-01-02'), identity(经代机构='另一平台'),
        identity(产品名称='另一产品'), identity(缴费年限='10'), identity(投保单号=None)])
    result = normalize_jingdai_source(source, source_format='policy_detail')
    assert result['承保件数'].iloc[:6].tolist() == [1, 0, 1, 1, 1, 1]
    assert pd.isna(result['承保件数'].iloc[-1])
    assert result['投保单号'].dropna().nunique() == 1
    assert result['期交保费'].sum() == source['期交保费'].sum()
    assert set(result['件数来源']) == {'policy_identity_daily'}


@pytest.mark.parametrize('value', ['5年', '终身', '-1', '1.5', 'inf', float('inf')])
def test_new_source_rejects_illegal_payment_years_without_zero_fill(value):
    with pytest.raises(ValueError, match='缴费年限'):
        normalize_jingdai_source(pd.DataFrame([identity(缴费年限=value)]), source_format='policy_detail')


@pytest.mark.parametrize('value', [None, ''])
def test_new_source_missing_payment_years_remains_unknown(value):
    result = normalize_jingdai_source(pd.DataFrame([identity(缴费年限=value)]), source_format='policy_detail')
    assert pd.isna(result['缴费年限'].iloc[0])
    assert result['当前缴别大类'].iloc[0] == '期交'


def test_lump_sum_frequency_is_explicit_and_term_flag_is_not_invented():
    result = normalize_jingdai_source(pd.DataFrame([identity(缴别='趸交', 缴费年限='0', 长短险='短险')]), source_format='policy_detail')
    assert result['当前缴别大类'].iloc[0] == '趸交'
    assert result['缴费年限'].iloc[0] == 0
    assert result['长短险'].iloc[0] == '短险'


def test_legacy_aliases_map_fields_and_preserve_signed_counts_without_fake_policy():
    old = pd.DataFrame([{'时间': '2020-05', '经代机构': '平台', '产品名称': '产品',
                         '承保年化规保': -100, '期交保费': -10, '承保产品件数': -2,
                         '当前缴别小类': '年交'}])
    result = normalize_jingdai_source(old)
    assert result['统计时间_年月日'].tolist() == ['2020-05']
    assert result['销售平台'].tolist() == ['平台']
    assert result['年化规保'].tolist() == [-100]
    assert result['缴别'].tolist() == ['年交']
    assert result['承保件数'].tolist() == [-2]
    assert result['投保单号'].isna().all()
    assert result['长短险'].isna().all()
    assert result['经代源格式'].tolist() == ['legacy_aggregate']
    assert result['件数来源'].tolist() == ['source_net']


def test_normalization_is_idempotent_and_database_null_identity_is_still_legacy():
    old = pd.DataFrame([{'时间': '2020-05-02', '经代机构': '平台', '产品名称': '产品',
                         '承保年化规保': 100, '期交保费': 10, '承保件数': 2,
                         '投保单号': None, '经代源格式': None}])
    result = normalize_jingdai_source(old)
    repeated = normalize_jingdai_source(result)
    pd.testing.assert_frame_equal(result, repeated)
    assert repeated['承保件数'].tolist() == [2]
    assert repeated['经代源格式'].tolist() == ['legacy_aggregate']


def test_mixed_persisted_sources_keep_their_own_count_bases():
    mixed = pd.DataFrame([dict(identity(), 经代源格式='policy_detail', 承保件数=99),
                          dict(identity(时间='2020-05-02', 投保单号=None), 经代源格式=None, 承保件数=-2)])
    result = normalize_jingdai_source(mixed)
    assert result['承保件数'].tolist() == [1, -2]
    assert result['件数来源'].tolist() == ['policy_identity_daily', 'source_net']


def test_legacy_payment_category_is_not_reinterpreted_from_payment_years():
    old = pd.DataFrame([{'时间': '2020-05-02', '经代机构': '平台', '产品名称': '产品',
                         '缴费年限': '1', '当前缴别大类': '', '当前缴别小类': '年交',
                         '期交保费': 10, '承保年化规保': 10, '承保件数': 1}])
    result = normalize_jingdai_source(old)
    assert result['缴费年限'].tolist() == ['1']
    assert result['当前缴别大类'].tolist() == ['']
