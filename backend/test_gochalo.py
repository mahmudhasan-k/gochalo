"""Gochalo upgrade regressions; all HTTP and DNS transports are mocked."""
import asyncio
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import types
import ai_service as service
import main
import url_input
from tests.fixtures import payload
from tests.test_semantic_review import scripted_review

SOURCE = "Fictional acceptance notice. Only current students who live in this district may apply. Submit certificate A OR certificate B unless already submitted. The fee is 200 taka, except applicants with disabilities pay no fee. All eligible applicants must submit the application form even when exempt from fees. Apply by 30 November 2026. Processing time is not stated."
SCOPE = "Only current students who live in this district may apply."
CERT = "Submit certificate A OR certificate B unless already submitted."
FEE = "The fee is 200 taka, except applicants with disabilities pay no fee."
FORM = "All eligible applicants must submit the application form even when exempt from fees."
DATE = "Apply by 30 November 2026."


def english_data():
    def claim(text, ref, conditions=()):
        return dict(text=text,evidence_ids=list(dict.fromkeys([ref]+(["e1"] if conditions else []))),status="source_stated",source_conditions=list(conditions))
    return dict(explanation=[claim(SCOPE,"e1")],
        steps=[claim(CERT,"e2"),claim("Submit the application form.","e3"),
               claim("Pay the fee of 200 taka if you are not an applicant with a disability.","e4")],
        documents=[claim(CERT,"e2"),claim("Submit the application form.","e3")],
        fees_and_deadlines=dict(fees=[claim(FEE,"e4",[SCOPE])],deadlines=[claim(DATE,"e5",[SCOPE])]),
        unknowns=[],evidence=[dict(id=f"e{i}",excerpt=quote) for i,quote in enumerate((SCOPE,CERT,FORM,FEE,DATE),1)])


def checked(data, source=SOURCE):
    return service.check_evidence(service.ProviderAnalysis.model_validate(data),source,
        source_type="user_provided",source_url=None,model="offline",output_language="en")


def apply(data, source=SOURCE, missing=None):
    result=checked(data,source)
    review=scripted_review(result,source,set(service.review_candidates(result)))
    # Separate precise review references, as required by the production schema.
    review.evidence=[service.Evidence(**e) for e in data["evidence"]]
    for d in review.decisions:
        item=service.review_candidates(result)[d.claim_id]
        d.evidence_ids=item.evidence_ids
        if missing and d.claim_id in missing:
            d.verdict="uncertain";d.missing_condition_ids=missing[d.claim_id]
    return service.apply_semantic_review(result,source,review,output_language="en")


def test_reproduces_exact_english_acceptance_source_and_admits_all_six_former_holds():
    ledger=json.loads((Path(__file__).parent/"engine/tests/data/source_fingerprints.json").read_text())
    assert hashlib.sha256(SOURCE.encode()).hexdigest()==ledger["cases"]["english-structured-context-3"]["source_sha256"]
    ids=["steps:0","steps:1","steps:2","documents:0","documents:1","deadlines:0"]
    public=main.public_result(apply(english_data(),missing={key:["e1"] for key in ids}))
    assert public["withheld_count"]==0
    assert [len(public["sections"][s]) for s in ("steps","documents","fees","deadlines")]==[3,2,1,1]


@pytest.mark.parametrize("condition",["e4","e5"])
def test_steps_need_not_repeat_fee_or_deadline_already_in_admitted_sections(condition):
    public=main.public_result(apply(english_data(),missing={"steps:1":[condition],"documents:1":[condition]}))
    assert len(public["sections"]["steps"])==3
    assert not any(u["reason_code"]=="missing_conditions" for u in public["unknowns"])


def test_unadmitted_date_or_fee_cannot_supply_shared_context():
    data=english_data();data["fees_and_deadlines"]["deadlines"][0]["status"]="unsupported"
    public=main.public_result(apply(data,missing={"steps:1":["e5"]}))
    assert "Submit the application form." not in [c["text"] for c in public["sections"]["steps"]]


def test_local_document_exception_cannot_be_dismissed_as_shared_context():
    data=english_data();data["steps"][0]["text"]="Submit certificate A OR certificate B."
    public=main.public_result(apply(data,missing={"steps:0":["e2"]}))
    assert not any(c["text"]==data["steps"][0]["text"] for c in public["sections"]["steps"])


@pytest.mark.parametrize("text",["Submit certificate A unless already submitted.",
    "Submit certificate A AND certificate B unless already submitted.",
    "Do not submit the application form.","Pay the fee of 999 taka.",
    "For residents of this district or current students, submit the application form."])
def test_fabrication_or_negation_and_alternative_reversal_stays_held_even_with_approval(text):
    data=english_data();data["steps"][0].update(text=text,evidence_ids=["e1","e2","e3","e4"])
    public=main.public_result(apply(data))
    assert text not in [c["text"] for c in public["sections"]["steps"]]


@pytest.mark.parametrize("original, excerpt",[
    ("Applicant’s record — bring ID.", "applicant's record - bring id."),
    ('The “student” service – open online.', 'THE "STUDENT" SERVICE - OPEN ONLINE'),
    ("Submit the form.", "...SUBMIT THE FORM!!!"),
    ("Keep your applicant's copy.", "KEEP YOUR APPLICANT’S COPY"),
])
def test_english_quote_typography_matches_and_display_uses_original_span(original,excerpt):
    data=payload();data["evidence"][0]["excerpt"]=excerpt
    result=checked(data,original)
    assert result.evidence[0].excerpt_found
    recovered=result.evidence[0].excerpt
    assert recovered in original
    assert service._quotation_key(recovered)==service._quotation_key(excerpt)


@pytest.mark.parametrize("excerpt",["Submit a passport copy", "Do not submit the form", "!!!"])
def test_quote_normalization_never_invents_words_or_erases_negation(excerpt):
    assert not service._quote_found(excerpt,"Submit the form.")


def ask_plan():
    return dict(explanation=["A general plan to correct a spelling mistake."],
        steps=["Check the official identity-service instructions.","Gather records showing the correct spelling."],
        documents=["Check which supporting records apply to your correction."],fees=[],deadlines=[],
        unknowns=[dict(category="fees",text="Confirm the current correction fee with the relevant office.")])


def test_ask_uses_one_real_sdk_mock_transport_request_and_no_source_review(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","offline-test-placeholder")
    calls=[]
    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={"candidates":[{"content":{"parts":[{"text":json.dumps(ask_plan())}],"role":"model"},"finishReason":"STOP"}]})
    client=service.genai.Client(vertexai=False,api_key="offline-test-placeholder",
        http_options=types.HttpOptions(api_version=service.API_VERSION,retry_options=types.HttpRetryOptions(attempts=1),
            client_args={"transport":httpx.MockTransport(respond)}))
    with patch.object(service.genai,"Client",return_value=client),patch.object(service,"REQUEST_BUDGET") as budget, \
         patch.object(service,"check_evidence",side_effect=AssertionError("No source gate for Ask")), \
         patch.object(service,"review_semantics",side_effect=AssertionError("No second call for Ask")):
        budget.wait_seconds.return_value=0
        result=service.analyze_ask("How do I correct a spelling mistake in my Bangladesh NID card online?",output_language="en")
    public=main.public_result(result)
    assert len(calls)==1
    assert "steps" in calls[0]["generationConfig"]["responseJsonSchema"]["properties"]
    assert public["review_mode"]=="general_ask" and public["semantic_review_complete"] is False
    assert public["has_guidance"] and public["evidence"]==[] and public["withheld_count"]==0
    assert public["sections"]["steps"][0]["evidence_ids"]==[]


@pytest.mark.parametrize("value",["", " ", "x"*2001])
def test_ask_engine_rejects_invalid_length_without_dispatch(value):
    with patch.object(service.genai,"Client") as call,pytest.raises(service.AnalysisError):
        service.analyze_ask(value)
    call.assert_not_called()


def test_ask_explanation_only_is_still_useful_information():
    data=ask_plan();data.update(steps=[],documents=[])
    assert main.public_result(service.GeneralAskResult(**data,output_language="en"))["has_guidance"]


@pytest.mark.parametrize("reviewed",[None,False,True])
def test_ask_api_accepts_unreviewed_question_with_owned_replay(reviewed):
    with TestClient(main.app) as client:
        h={"X-Session-Token":client.post("/api/session").json()["token"]}
        body=dict(text="How to open a student bank account?",kind="ask",language="en",revision="ask-r1",request_id="ask-once")
        if reviewed is not None:body["reviewed"]=reviewed
        result=service.GeneralAskResult(**ask_plan(),output_language="en")
        with patch.object(service,"analyze_ask",return_value=result) as generate,patch.object(service,"analyze_instructions",side_effect=AssertionError("notice path")):
            job=client.post("/api/analysis",json=body,headers=h)
            assert job.status_code==202
            job_id=job.json()["job_id"]
            for _ in range(100):
                value=client.get("/api/jobs/"+job_id,headers=h).json()
                if value["status"] in ("succeeded","failed"):break
                time.sleep(.01)
            assert value["status"]=="succeeded" and value["result"]["review_mode"]=="general_ask"
            assert client.post("/api/analysis",json=body,headers=h).json()["job_id"]==job_id
            assert client.get("/api/jobs/"+job_id).status_code==401
            generate.assert_called_once()
            assert client.post("/api/analysis",json={**body,"text":"x"*2001},headers=h).status_code==422


@pytest.mark.parametrize("domain",["example.edu","university.ac.bd","bank.com","scholarship.org","gov.bd","example.gov.bd.evil.test"])
def test_public_domains_are_admitted_without_suffix_authority(domain):
    assert url_input.normalize_url("https://"+domain+"/apply")=="https://"+domain+"/apply"


@pytest.mark.parametrize("address",["127.0.0.1","10.0.0.1","172.16.0.1","192.168.0.1","169.254.169.254","::1","fe80::1","fc00::1","0.0.0.0"])
def test_public_domain_resolving_to_private_address_stays_blocked(address):
    async def resolve(_):return (address,)
    with pytest.raises(url_input.ExtractionError):
        asyncio.run(url_input._public_url("https://bank.com/",resolve))


def test_general_page_and_reported_destination_are_public_dns_checked_once():
    calls=[];hosts=[]
    async def resolve(host):hosts.append(host);return ("8.8.8.8",)
    def respond(request):
        calls.append(request)
        assert request.headers["X-Respond-With"]=="markdown"
        return httpx.Response(200,json={"code":200,"data":{"content":"University admissions: submit by 30 November.","url":"https://university.edu/apply"}})
    value=asyncio.run(url_input.extract_url("https://university.edu/pages/admission",session=url_input.ExtractionSession(),
        budget=url_input.ExtractionBudget(),transport=httpx.MockTransport(respond),resolver=resolve))
    assert value.text.startswith("University admissions")
    assert len(calls)==1 and hosts==["university.edu","university.edu"]



def test_live_followup_fees_and_dates_share_explicit_reviewed_global_overview():
    data=english_data()
    for section in ("fees","deadlines"):
        data["fees_and_deadlines"][section][0]["source_conditions"]=[]
        data["fees_and_deadlines"][section][0]["evidence_ids"]=["e4" if section=="fees" else "e5"]
    public=main.public_result(apply(data))
    assert public["withheld_count"]==0
    assert len(public["sections"]["fees"])==len(public["sections"]["deadlines"])==1
    assert len(public["sections"]["steps"])==3


def test_deterministic_only_plan_does_not_require_repeating_global_overview():
    result=checked(english_data())
    public=main.public_result(service.deterministic_review_fallback(result,TimeoutError(),source_text=SOURCE))
    assert len(public["sections"]["steps"])==3
    assert public["review_mode"]=="deterministic_only" and not public["semantic_review_complete"]



def test_misrouted_reviewed_fee_is_not_shared_as_admitted_fee_context():
    data=english_data();result=checked(data)
    review=scripted_review(result,SOURCE,set(service.review_candidates(result)))
    review.evidence=[service.Evidence(**e) for e in data["evidence"]]
    for decision in review.decisions:
        decision.evidence_ids=service.review_candidates(result)[decision.claim_id].evidence_ids
        if decision.claim_id=="fees:0":decision.section="documents"
        if decision.claim_id=="steps:1":
            decision.verdict="uncertain";decision.missing_condition_ids=["e4"]
    public=main.public_result(service.apply_semantic_review(result,SOURCE,review,output_language="en"))
    assert not public["sections"]["fees"]
    assert "Submit the application form." not in [c["text"] for c in public["sections"]["steps"]]
