"""Synthetic read-only-code review reproductions. All SQL databases are :memory:."""
import sys,os,io,json,sqlite3
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
sys.dont_write_bytecode=True
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'backend'))
os.environ['BUSINESS_ANALYSIS_DB']=':memory:'
import pandas as pd
from etl.aggregates.dashboard import aggregate_staff_month_performance,aggregate_jingdai_product_daily
from etl.aggregates.hr import aggregate_active_headcount
from etl.aggregates.longterm import aggregate_transform_longterm
from etl.aggregates.performance import aggregate_performance
from metrics.business_rules import is_longterm_policy
from db.repositories.team_enhanced import _load_performance
from db.repositories.product import _query_product_daily_aggregate
from db.repositories.kpi import get_kpi_data
from db import schema
from config.orgs import ORG_LIST
from services.excel_pipeline import ExcelSource,build_excel_pipeline_result,write_excel_pipeline_result
from services.import_preview import build_import_preview
from validators.data_validator import validate_rows

def emit(key,obj): print(key+': '+json.dumps(obj,ensure_ascii=False,default=str))
def memory():
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;return c

def initialized():
 c=memory()
 with patch.object(schema,'get_db',lambda:nullcontext(c)), patch('auth.ensure_default_admin',lambda:None): schema.init_db()
 return c

base={'年':2026,'年月':'2026-09','业务模式':'OTO','人员工号':'SYNTHETIC-DEMO','期交保费':10000,'折算保费':10000,'长短险':'长期','产品代码':'DEMO','缴费年限':5,'投保单号':'SYNTHETIC-P1','销售机构名称':ORG_LIST[0],'承保件数':1}
c=memory();frame=pd.DataFrame([base,dict(base,业务模式='证保',期交保费=0,折算保费=0)])
frame.to_sql('performance',c,index=False);pd.DataFrame(aggregate_staff_month_performance(frame)).to_sql('agg_staff_month_performance',c,index=False)
agg=list(_load_performance(c,2026,None,None).values());c.execute('DROP TABLE agg_staff_month_performance');raw=list(_load_performance(c,2026,None,None).values())
emit('M1_same_policy_cross_channel',{'aggregate':agg,'raw':raw});assert agg[0]['policy_count']==2 and raw[0]['policy_count']==1
conflict=dict(base,长短险='短期',产品代码='4281',缴费年限=1)
textpay=dict(base,长短险='',缴费年限='5年')
emit('M2_ONLY_conflict_or_text_term',{'shortterm4281_shared':is_longterm_policy('短期','4281',1),'shortterm4281_etl':aggregate_transform_longterm(pd.DataFrame([conflict])),'text5years_longterm':aggregate_transform_longterm(pd.DataFrame([textpay])),'text5years_active':aggregate_active_headcount(pd.DataFrame([textpay]))})
# Full workbook -> preview -> parse -> transaction write, with an initialized empty synthetic DB.
buf=io.BytesIO();pd.DataFrame([base]).to_excel(buf,index=False);source=ExcelSource('performance','synthetic.xlsx',buf.getvalue());c=initialized()
preview=build_import_preview(c,[source]);parsed=build_excel_pipeline_result([source]);written=write_excel_pipeline_result(c,parsed,incremental=True)
emit('M3_full_import_month_only',{'preview_canImport':preview['canImport'],'preview_errors':preview['errors'],'daily_rows':[dict(r) for r in c.execute('SELECT year,month,day,qj_premium FROM agg_daily_performance')],'activity_rows':[dict(r) for r in c.execute('SELECT year,month,day,uncertain FROM agg_org_daily_activity')]});assert preview['canImport'];assert c.execute('SELECT day FROM agg_daily_performance').fetchone()[0]==1
rev=dict(base,期交保费=-10000,折算保费=-10000,承保件数=-1)
emit('M4_gross_vs_net_activity',{'net_premium':0,'legacy_activity':aggregate_active_headcount(pd.DataFrame([base,rev])),'enhanced_activity_rule':0>0})
jd=pd.DataFrame([{'时间':'2026-09-10','产品名称':'SYNTHETIC','期交保费':10000},{'时间':'2026-09-10','产品名称':'SYNTHETIC','期交保费':-10000}])
emit('M5_jingdai_record_count',aggregate_jingdai_product_daily(jd))
invalid=aggregate_performance(pd.DataFrame([dict(base,期交保费='1,000')]))
emit('M6_invalid_numeric',{'raw_amount':'1,000','aggregated':invalid,'validation':validate_rows(invalid,required=['year','month','channel']).to_dict()})
# Product mix with 21 products: verify returned total omits one without an other bucket.
c=memory();rows=[]
for i in range(21): rows.append({'year':2026,'month':9,'day':10,'business_type':'经代','channel':'经代','org':'SYNTHETIC','product_category':f'P{i:02d}','product_name':f'P{i:02d}','qj_premium':1.0,'gm_premium':1.0,'count':1})
pd.DataFrame(rows).to_sql('agg_product_daily',c,index=False)
res=_query_product_daily_aggregate(c,2026,['OTO'],[],False,True,orgs=None,months=None,metric_type='qj',start_cutoff=(1,1),end_cutoff=(9,10))
emit('M7_top20_mix_truncation',{'source_total':21,'returned_total':sum(r['premium'] for r in res[0]),'returned_rows':len(res[0]),'other_bucket':any(r['label']=='其他' for r in res[0])})
# Current KPI uses daily payment when any row in that year exists (not scoped to jingdai).
c=initialized()
c.execute("INSERT INTO agg_daily_performance(year,month,day,channel,qj_premium) VALUES (2026,9,10,'OTO',1)")
c.execute("INSERT INTO agg_jingdai_daily(year,month,day,ymd,qj_premium) VALUES (2026,9,10,'2026-09-10',1)")
c.execute("INSERT INTO agg_payment_period(year,month,business_type,channel,category,qj_premium) VALUES (2026,9,'经代','','10年及以上',7)")
c.execute("INSERT INTO agg_performance(year,month,channel,qj_premium) VALUES (2026,9,'OTO',1)")
a=get_kpi_data(2026,as_of='2026-09-10',connection_override=c)
emit('M8_no_daily_payment_fallback',{'tenyear_jd':a['tenyear_jd'],'precision':a['metric_sources']['tenyear_jingdai_precision'],'card_warning':a['metrics']['cards']['10year']['jingdai'].get('warning')})
c.execute("INSERT INTO agg_payment_period_daily(year,month,day,business_type,channel,category,qj_premium) VALUES (2026,9,10,'转型','OTO','10年及以上',1)")
b=get_kpi_data(2026,as_of='2026-09-10',connection_override=c)
emit('M8_only_transform_daily_suppresses_jd_fallback',{'tenyear_jd':b['tenyear_jd'],'precision':b['metric_sources']['tenyear_jingdai_precision'],'card_warning':b['metrics']['cards']['10year']['jingdai'].get('warning')})
print('DONE: synthetic evidence only; no production connection.')


