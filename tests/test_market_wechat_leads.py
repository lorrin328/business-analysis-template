from market_analysis.wechat_leads import retain_leads, apply_lead_reviews, safe_article_url
from run_market_research import apply_source_scout_metadata, build_prompt


def lead():
    return {'title':'公众号观察','publisher':'行业观察号','url':'https://mp.weixin.qq.com/s/example',
            'claim':'作者认为养老需求发生变化','materialType':'snippet'}


def test_access_failure_keeps_information_instead_of_dismissing_it():
    row={**lead(),'id':'H1','sourceType':'official_wechat'}
    rows=retain_leads([], [row], [{'id':'H1','category':'access_controlled'}])
    assert rows[0]['claim']==row['claim']
    assert rows[0]['status']=='unresolved'
    assert 'access_controlled' in rows[0]['accessNote']


def test_nonofficial_snippet_without_full_body_is_retained_and_deduplicated():
    assert len(retain_leads([lead(),lead()],[],[]))==1
    assert retain_leads([{**lead(),'url':''}],[],[])[0]['publisher']=='行业观察号'


def test_private_or_credential_urls_are_not_persisted():
    assert not safe_article_url('https://mp.weixin.qq.com/s/example?token=secret')
    assert not safe_article_url('https://mp.weixin.qq.com@127.0.0.1/s/example')
    assert not safe_article_url('http://mp.weixin.qq.com/s/example')


def test_retained_leads_reach_main_research_and_published_reference_section():
    scout={'enabled':True,'completed':True,'wechatLeads':retain_leads([lead()],[],[])}
    report={}
    apply_source_scout_metadata(report,scout)
    assert report['wechatLeads'][0]['claim']==lead()['claim']
    assert '作者认为养老需求发生变化' in build_prompt({},[],[],source_scout=scout)
    assert 'sources' not in report  # Leads do not inflate verified-source counts.


def test_model_support_requires_independently_verified_comparison_source():
    rows=retain_leads([lead()],[],[])
    source={'id':'S1','url':'https://example.com/report','sourceLevel':'B','sourceType':'company'}
    report={'sources':[source],'wechatLeadReviews':[{'leadId':'WL1','status':'supported','assessment':'官网支持其中的产品动作', 'evidenceIds':['S1']}]}
    apply_lead_reviews(report,rows)
    assert report['wechatLeads'][0]['status']=='unresolved'
    source['verification']={'status':'verified'}
    apply_lead_reviews(report,rows)
    assert report['wechatLeads'][0]['status']=='supported'
    source['url']=lead()['url']
    apply_lead_reviews(report,rows)
    assert report['wechatLeads'][0]['status']=='unresolved'  # Original is not independent corroboration.


def test_conflict_and_partial_support_remain_distinct_from_falsehood():
    rows=retain_leads([lead()],[],[])
    for status in ['partial','conflicting']:
        report={'sources':[{'id':'S2','sourceType':'media','url':'https://example.com/b','verification':{'status':'verified'}}],
                'wechatLeadReviews':[{'leadId':'WL1','status':status,'assessment':'不同口径，仍需复核','evidenceIds':['S2']}]}
        apply_lead_reviews(report,rows)
        assert report['wechatLeads'][0]['status']==status
