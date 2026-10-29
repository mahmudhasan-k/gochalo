"""Offline regression evidence for the General Ask iteration. No live datasets."""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types
from pydantic import SecretStr

import ai_service as ai
import gemini_requests as pool
import main
from portal_content import portal_text
from request_control import BudgetExceeded
from result_contract import finalize, ORDER
from source_inventory import extract_inventory, source_sections


def settings():
    return ai.Settings(api_key=SecretStr("offline-primary"), model=ai.DEFAULT_MODEL)


def response(data):
    return SimpleNamespace(text=json.dumps(data), candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)])


def quota():
    return errors.ClientError(429, {"error":{"code":429,"status":"RESOURCE_EXHAUSTED","message":"PRIVATE input/credential"}})


def call_pool(monkeypatch, outcomes, *, backups=("offline-backup-1", "offline-backup-2")):
    for i, key in enumerate(backups, 1):
        monkeypatch.setenv(f"GEMINI_BACKUP_API_KEY_{i}", key)
    calls=[]
    def client(**kwargs):
        assert kwargs["http_options"].retry_options.attempts == 1
        key=kwargs["api_key"]
        def generate(**payload):
            calls.append((key, payload))
            outcome=outcomes[key]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return MagicMock(__enter__=lambda _:SimpleNamespace(models=SimpleNamespace(generate_content=generate)),
                         __exit__=lambda *args:False)
    monkeypatch.setattr(ai.genai,"Client",client)
    budget=MagicMock();budget.wait_seconds.return_value=0
    monkeypatch.setattr(ai,"REQUEST_BUDGET",budget)
    return calls, budget


def dispatch(stage="general_ask"):
    return pool.generate(settings(),contents="private goal",config=types.GenerateContentConfig(temperature=0),stage=stage,tokens=100)


def test_backup_order_same_payload_shared_budget_and_secret_free_ledger(monkeypatch, caplog):
    expected=response({"ok":True})
    calls,budget=call_pool(monkeypatch,{"offline-primary":quota(),"offline-backup-1":quota(),"offline-backup-2":expected})
    ledger=[];token=pool.attempt_log.set(ledger)
    try:
        assert dispatch() is expected
    finally:
        pool.attempt_log.reset(token)
    assert [key for key,_ in calls] == ["offline-primary","offline-backup-1","offline-backup-2"]
    assert calls[0][1] == calls[1][1] == calls[2][1]
    assert len({c.args[0] for c in budget.reserve.call_args_list}) == 1
    assert [e["attempt"] for e in ledger] == [1,2,3]
    assert [e["slot"] for e in ledger] == ["primary","backup_1","backup_2"]
    assert "offline-" not in json.dumps(ledger)
    assert "private goal" not in json.dumps(ledger)
    assert "PRIVATE" not in caplog.text


def test_duplicate_keys_are_not_retried(monkeypatch):
    calls,_=call_pool(monkeypatch,{"offline-primary":quota()},backups=("offline-primary","offline-primary"))
    with pytest.raises(ai.AnalysisError):dispatch()
    assert len(calls)==1


def test_only_next_failed_stage_uses_available_backup(monkeypatch):
    calls,_=call_pool(monkeypatch,{"offline-primary":quota(),"offline-backup-1":response({})})
    dispatch("source_generation")
    dispatch("semantic_review")
    assert [key for key,_ in calls] == ["offline-primary","offline-backup-1","offline-backup-1"]


@pytest.mark.parametrize("failure",[
    errors.ClientError(400,{"error":{"message":"bad schema"}}),
    errors.ClientError(401,{"error":{"message":"invalid key"}}),
    errors.ClientError(403,{"error":{"message":"permission"}}),
    httpx.ReadTimeout("timeout"),
])
def test_non_quota_errors_do_not_rotate(monkeypatch,failure):
    calls,_=call_pool(monkeypatch,{"offline-primary":failure})
    with pytest.raises(type(failure)):dispatch()
    assert len(calls)==1


@pytest.mark.parametrize('status',[500,502,503,504])
def test_service_errors_rotate_same_stage_once_per_key_with_backoff(monkeypatch,status):
    error=errors.ServerError(status,{'error':{'code':status,'message':'PRIVATE'}})
    calls,_=call_pool(monkeypatch,{'offline-primary':error,'offline-backup-1':error,'offline-backup-2':response({})})
    clock=[0.0];pauses=[]
    monkeypatch.setattr(pool,'monotonic',lambda:clock[0])
    def pause(seconds):pauses.append(seconds);clock[0]+=seconds
    monkeypatch.setattr(ai,'sleep',pause)
    dispatch('semantic_review')
    assert [key for key,_ in calls]==['offline-primary','offline-backup-1','offline-backup-2']
    assert calls[0][1]==calls[1][1]==calls[2][1]
    assert pauses==[1.5,1.5]


def test_service_exhaustion_is_bounded_and_does_not_restart_generation(monkeypatch):
    error=errors.ServerError(503,{'error':{'code':503,'message':'PRIVATE'}})
    calls,_=call_pool(monkeypatch,{key:error for key in ('offline-primary','offline-backup-1','offline-backup-2')})
    monkeypatch.setattr(ai,'sleep',lambda _:None)
    with pytest.raises(ai.AnalysisError) as caught:dispatch('semantic_review')
    assert caught.value.code=='service_busy' and not ai._fallback_eligible(caught.value)
    assert len(calls)==3


def test_local_budget_does_not_rotate_or_dispatch(monkeypatch):
    calls,budget=call_pool(monkeypatch,{})
    budget.reserve.side_effect=BudgetExceeded("local_rate_limit","local guard")
    with pytest.raises(BudgetExceeded):dispatch()
    assert calls==[]


def test_exhaustion_is_bounded_and_cooldowns_prevent_repeat_dispatch(monkeypatch):
    calls,_=call_pool(monkeypatch,{key:quota() for key in ("offline-primary","offline-backup-1","offline-backup-2")})
    with pytest.raises(ai.AnalysisError) as error:dispatch()
    assert error.value.code == "rate_limit_or_quota" and not ai._fallback_eligible(error.value)
    assert len(calls)==3
    with pytest.raises(ai.AnalysisError, match="temporarily unavailable"):dispatch()
    assert len(calls)==3


def test_deadline_prevents_any_dispatch(monkeypatch):
    calls,_=call_pool(monkeypatch,{})
    token=pool.job_deadline.set(time.monotonic()-1)
    try:
        with pytest.raises(ai.AnalysisError) as error:dispatch()
    finally:
        pool.job_deadline.reset(token)
    assert error.value.code=="job_timeout" and calls==[]


def test_provider_retry_after_and_retry_info_are_respected():
    error=quota()
    error.response=httpx.Response(429,headers={'Retry-After':'125'})
    assert pool._cooldown(error)==125
    error.response=None
    error.details={'error':{'details':[{'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':'91.5s'}]}}
    assert pool._cooldown(error)==91.5
    error.details={}
    assert pool._cooldown(error)==60


def test_evaluation_trace_redacts_credentials_and_bounds_without_silent_truncation(monkeypatch):
    from evaluation_trace import sink,record
    monkeypatch.setenv('GEMINI_API_KEY','secret-primary')
    trace=[];token=sink.set(trace)
    try:
        record('test',input='Source secret-primary',headers={'authorization':'secret-primary'},image=b'pixels')
        record('large',output='x'*1_100_000)
    finally:
        sink.reset(token)
    assert 'secret-primary' not in json.dumps(trace)
    assert 'authorization' not in json.dumps(trace)
    assert trace[-1]['coverage']=='trace_size_limit'


def test_scoped_document_exception_and_alternative_survive_but_missing_exception_fails():
    source="Submit a student card OR a letter. A previously verified card need not be submitted again."
    item=ai.Claim(text="Submit a student card OR a letter.",source_conditions=[source.split('. ')[1]],evidence_ids=["e1"],status="source_stated")
    assert ai.deterministic_requirement_reason(item,"documents",source,source) is None
    assert ai.deterministic_requirement_reason(item.model_copy(update={"source_conditions":[]}),"documents",source,source)=="document_negation"
    prohibition="Do not submit originals."
    bad=ai.Claim(text="Submit originals.",evidence_ids=["e1"],status="source_stated")
    assert ai.deterministic_requirement_reason(bad,"documents",prohibition,prohibition)=="document_negation"
    assert ai.deterministic_requirement_reason(bad.model_copy(update={"text":prohibition}),"steps",prohibition,prohibition) is None


def test_unrelated_document_negation_does_not_erase_form_requirement():
    source="Submit the form. A previously verified card need not be submitted again."
    item=ai.Claim(text="Submit the form.",evidence_ids=["e1"],status="source_stated")
    assert ai.deterministic_requirement_reason(item,"documents",source,source) is None


def test_long_source_partition_is_lossless_and_inventory_recovers_original_whitespace(monkeypatch):
    source=("Section heading\n\n"+"useful paragraph. "*650)+"\nSubmit\nthe form."
    sections=source_sections(source)
    assert ''.join(s['text'] for s in sections)==source
    assert len(sections)>1 and max(len(s['text']) for s in sections)<=8000
    data={"sections":[{"section_id":s['section_id'],"facts":
          [{"category":"documents","source_quote":"Submit the form."}] if 'Submit\nthe form.' in s['text'] else []} for s in sections]}
    monkeypatch.setattr(ai,"gemini_generate",lambda *a,**k:response(data))
    inventory=extract_inventory(source,settings=settings(),language="en")
    assert inventory['sections'][-1]['facts'][0]['source_quote']=='Submit\nthe form.'


def test_inventory_drops_cross_section_facts_and_tolerates_missing_sections(monkeypatch):
    source="a"*8000+"\nA material requirement."
    parts=source_sections(source)
    data={"sections":[{"section_id":s['section_id'],"facts":[]} for s in parts]}
    data['sections'][0]['facts']=[{"category":"steps","source_quote":"A material requirement."}]
    monkeypatch.setattr(ai,"gemini_generate",lambda *a,**k:response(data))
    assert extract_inventory(source,settings=settings(),language="en")['sections'][0]['facts']==[]
    data['sections'].pop()
    assert len(extract_inventory(source,settings=settings(),language="en")['sections'])==1


def test_projection_keeps_legacy_arrays_and_scoped_conflicts_without_fake_sources():
    sections={key:[] for key in ("explanation","steps","documents","fees","deadlines")}
    sections['steps']=[{"text":"Prepare.","evidence_ids":[]}]
    output=dict(review_mode="general_ask",sections=sections,evidence=[],section_states={},unknowns=[
        dict(kind="unverified",category="fees",text="Check the fee.",evidence_ids=[]),
        dict(kind="unverified",category="fees",text="Check the fee.",evidence_ids=[]),
        dict(kind="unverified",category="fees",text="Check the exemption.",evidence_ids=[])])
    result=finalize(output)
    assert result['sections'] is sections and len(result['unknowns'])==2
    assert result['category_order']==list(ORDER)
    assert result['sections']['steps'][0]['support_status']=='unreviewed'
    assert result['evidence']==[] and 'categories' not in result
    output['evidence']=[{'id':'e1','excerpt':'Two disputed dates in the same paragraph.'}]
    output['unknowns']=[dict(kind='contradiction',category='deadlines',text=text,evidence_ids=['e1']) for text in ('The opening date conflicts.','The closing date conflicts.')]
    assert len(finalize(output)['unknowns'])==2


def test_cleaning_preserves_forms_tables_headers_and_footnotes():
    text=portal_text('<nav>Menu</nav><article><header>Deadline: 12 November</header><form><p>Submit the form.</p></form><table><tr><td>Fee</td><td>50</td></tr></table><footer>Exemption: returning applicants.</footer></article>','https://example.org/')
    for fact in ('Deadline: 12 November','Submit the form.','Fee','50','Exemption: returning applicants.'):
        assert fact in text
    assert 'Menu' not in text


def test_material_coverage_gaps_remain_original_passages_in_others_not_new_requirements():
    from tests.fixtures import SOURCE,payload
    from tests.test_semantic_review import scripted_review
    extra='Sessions last 90 minutes. Do not remove equipment.'
    source=SOURCE+'\n'+extra
    checked=ai.check_evidence(ai.ProviderAnalysis.model_validate(payload()),source,source_type='user_provided',source_url=None,model=ai.DEFAULT_MODEL)
    checked=ai.apply_semantic_review(checked,source,scripted_review(checked,source,set(ai.review_candidates(checked))))
    enriched=ai.add_coverage_gaps(checked,source,[ai.CoverageGap(category='deadlines',source_quote=extra)],'en')
    output=main.public_result(enriched)
    assert any(u['category']=='deadlines' and u['kind']=='unverified' for u in output['unknowns'])
    assert any(e['excerpt']==extra for e in output['evidence'])
    assert not any(extra==row['text'] for rows in output['sections'].values() for row in rows)
    skipped=ai.add_coverage_gaps(checked,source,[ai.CoverageGap(category='fees',source_quote='Invented fee.')],'en')
    assert skipped.model_dump()==checked.model_dump()


def test_job_deadline_withholds_a_completed_answer_after_expiry(monkeypatch):
    clock=[0.0]
    monkeypatch.setattr(main,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def generate(*args,**kwargs):
        clock[0]=601
        return ai.GeneralAskResult(explanation=['Late answer'],steps=['Late action'],documents=[],fees=[],deadlines=[],unknowns=[],output_language='en')
    monkeypatch.setattr(ai,'analyze_ask',generate)
    with TestClient(main.app) as client:
        h={'X-Session-Token':client.post('/api/session').json()['token']}
        job=client.post('/api/analysis',json=dict(text='Offline goal.',kind='ask',language='en',revision='deadline'),headers=h).json()['job_id']
        state=wait(client,job,h)
        assert state['status']=='failed' and state['error']=='job_timeout' and state['result'] is None


def wait(client,job,headers):
    for _ in range(200):
        value=client.get('/api/jobs/'+job,headers=headers).json()
        if value['status'] in ('succeeded','failed'):return value
        time.sleep(.005)
    pytest.fail('offline job did not complete')


def test_large_owned_source_reference_preserves_byte_guard_and_mode(monkeypatch):
    source='ক'*49000
    async def extract(*args,**kwargs):
        from datetime import datetime,timezone
        return SimpleNamespace(text=source,requested_url='https://example.org/',returned_url='https://example.org/',retrieved_at=datetime.now(timezone.utc),title='Source')
    monkeypatch.setattr(main.url_input,'extract_url',extract)
    seen=[]
    def analyze(text,**kwargs):
        seen.append(text)
        return ai.GeneralAskResult(explanation=['Offline stub'],steps=[],documents=[],fees=[],deadlines=[],unknowns=[],output_language='en')
    monkeypatch.setattr(ai,'analyze_instructions',analyze)
    with TestClient(main.app) as client:
        headers={'X-Session-Token':client.post('/api/session').json()['token']}
        job=client.post('/api/extract/link',json={'url':'https://example.org/','revision':'r1'},headers=headers).json()['job_id']
        assert wait(client,job,headers)['status']=='succeeded'
        body=dict(extraction_job_id=job,kind='link',language='en',revision='r2')
        other={'X-Session-Token':client.post('/api/session').json()['token']}
        assert client.post('/api/analysis',json=body,headers=other).status_code==422
        assert client.post('/api/analysis',json={**body,'kind':'image'},headers=headers).status_code==422
        assert client.post('/api/analysis',json={**body,'text':'edited'},headers=headers).status_code==422
        oversized=json.dumps(dict(text=source,kind='text',language='en',revision='r2'),ensure_ascii=False).encode()
        assert client.post('/api/analysis',content=oversized,headers={**headers,'Content-Type':'application/json'}).status_code==413
        result=client.post('/api/analysis',json=body,headers=headers)
        assert result.status_code==202
        assert wait(client,result.json()['job_id'],headers)['status']=='succeeded'
        assert seen==[source]
        assert client.get('/api/jobs/'+job+'/diagnostics',headers=other).status_code==404
        assert client.get('/api/jobs/'+job+'/diagnostics',headers=headers).json()=={'attempts':[]}
