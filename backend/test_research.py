"""Research provenance, bounded provider work and automatic-source admission."""
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import types

import ai_service as ai
import main
import research


def response(text="Use a checklist.", *, grounded=True):
    metadata=types.GroundingMetadata(web_search_queries=["planning"],
        grounding_chunks=[types.GroundingChunk(web=types.GroundingChunkWeb(uri="https://example.org/guide",title="Guide"))],
        grounding_supports=[types.GroundingSupport(segment=types.Segment(start_index=0,end_index=len(text.encode()),text=text),grounding_chunk_indices=[0])],
        search_entry_point=types.SearchEntryPoint(rendered_content="<div>Search attribution</div>")) if grounded else None
    return types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="STOP",
        content=types.Content(parts=[types.Part(text=text)]),grounding_metadata=metadata)])


def plan():
    return research.ResearchPlan(title="Prepare your week",explanation=[],
        steps=[research.ResearchItem(text="Use a checklist.",support_ids=["g1"]),
               research.ResearchItem(text="Choose a quiet hour.",suggestion=True)],
        documents=[],fees=[],deadlines=[],unknowns=[])


def wait(client,headers,job):
    for _ in range(100):
        value=client.get("/api/jobs/"+job,headers=headers).json()
        if value["status"] in ("failed","succeeded"):return value
        time.sleep(.01)
    pytest.fail("job did not finish")


def test_grounding_support_offsets_preserve_bangla_and_provider_links():
    sources,supports,attribution=research.collect_grounding(response("কাজ গুছিয়ে নিন।"))
    assert sources==[{"id":"s1","url":"https://example.org/guide","title":"Guide"}]
    assert supports==[{"id":"g1","text":"কাজ গুছিয়ে নিন।","source_ids":["s1"]}]
    assert "attribution" in attribution


def test_citations_use_the_referenced_text_part_and_never_thought_parts():
    value=response()
    value.candidates[0].content.parts.insert(0,types.Part(text="Private reasoning",thought=True))
    value.candidates[0].grounding_metadata.grounding_supports[0].segment.part_index=1
    assert research.collect_grounding(value)[1][0]["text"]=="Use a checklist."
    value.candidates[0].grounding_metadata.grounding_supports[0].segment.part_index=0
    fallback=research.collect_grounding(value)[1][0]
    assert fallback['unverified'] is True and fallback['source_ids']==[]
    assert 'Private reasoning' not in fallback['text']


@pytest.mark.parametrize("change",["no_grounding","bad_offset","invented_excerpt","no_source","no_query","unsafe_url"])
def test_unusable_grounding_becomes_unverified_without_fabricated_citations(change):
    value=response(grounded=change!="no_grounding")
    if change=="bad_offset":value.candidates[0].grounding_metadata.grounding_supports[0].segment.end_index=9999
    if change=="invented_excerpt":value.candidates[0].grounding_metadata.grounding_supports[0].segment.text="Not the response"
    if change=="no_source":value.candidates[0].grounding_metadata.grounding_chunks=[]
    if change=="no_query":value.candidates[0].grounding_metadata.web_search_queries=[]
    if change=="unsafe_url":value.candidates[0].grounding_metadata.grounding_chunks[0].web.uri="javascript:alert(1)"
    sources,supports,_=research.collect_grounding(value)
    if change=='no_query':
        assert supports[0]['source_ids']==['s1']  # Actual provider citation mapping still exists.
    else:
        assert supports[0]['source_ids']==[] and supports[0]['unverified'] is True


def test_result_separates_suggestions_and_withholds_invalid_citations_and_unsourced_fees():
    sources,supports,attribution=research.collect_grounding(response())
    value=plan();value.steps.append(research.ResearchItem(text="Invented",support_ids=["g999"]))
    value.fees=[research.ResearchItem(text="Free",suggestion=True)]
    output=research.public_plan(value,sources,supports,attribution,"en")
    assert output["review_mode"]=="web_research" and output["semantic_review_complete"] is False
    assert output["evidence"]==[] and output["source_reviewed"] is False
    assert output["sections"]["steps"][0]["source_ids"]==["s1"]
    assert output["sections"]["steps"][1]["support_status"]=="planning_suggestion"
    assert output["sections"]["fees"][0]['support_status']=='planning_suggestion'
    assert output["sections"]["fees"][0]['source_ids']==[] and output["withheld_count"]==1
    assert "Invented" not in json.dumps(output)


def test_research_is_two_explicit_provider_requests_with_no_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","offline-fake-key");monkeypatch.setenv("RESEARCH_FREE_ACCESS_CONFIRMED","true")
    client=MagicMock();client.models.generate_content.side_effect=[response(),response(plan().model_dump_json())]
    with patch.object(ai.genai,"Client") as factory,patch.object(ai,"REQUEST_BUDGET"):
        factory.return_value.__enter__.return_value=client
        output=research.analyze_research("Plan the week",output_language="en",context="At home")
    assert client.models.generate_content.call_count==2
    calls=client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"]=="gemini-2.5-flash"
    assert calls[0].kwargs["config"].tools[0].google_search is not None
    assert calls[1].kwargs["model"]==ai.DEFAULT_MODEL
    assert output["title"]=="Prepare your week"


def test_unmapped_research_text_plans_with_unverified_labels_and_never_quick_plan(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","offline-fake-key");monkeypatch.setenv("RESEARCH_FREE_ACCESS_CONFIRMED","true")
    client=MagicMock();client.models.generate_content.side_effect=[response(grounded=False),response(plan().model_dump_json())]
    with patch.object(ai.genai,"Client") as factory,patch.object(ai,"REQUEST_BUDGET"),patch.object(ai,"analyze_ask") as quick:
        factory.return_value.__enter__.return_value=client
        output=research.analyze_research("Plan")
    assert client.models.generate_content.call_count==2
    assert output['citation_supports']==[]
    assert all(c['support_status']=='planning_suggestion' and c['source_ids']==[] for c in output['sections']['steps'])
    quick.assert_not_called()


def test_api_research_owned_replay_validation_and_disabled_gate():
    with TestClient(main.app) as client:
        headers={"X-Session-Token":client.post("/api/session").json()["token"]}
        body={"query":"Plan the week","context":"","language":"en","revision":"r1","request_id":"q1"}
        assert client.post("/api/research",json=body).status_code==401
        assert client.post("/api/research",json=body,headers=headers).json()=={"detail":"research_unavailable"}
        assert client.post("/api/research",json={**body,"query":" "},headers=headers).status_code==422
        assert client.post("/api/research",json={**body,"context":"private"*501},headers=headers).json()=={"detail":"invalid_input"}
        sources,supports,attr=research.collect_grounding(response())
        result=research.public_plan(plan(),sources,supports,attr,"en")
        with patch.object(research,"enabled",return_value=True),patch.object(research,"analyze_research",return_value=result) as provider:
            first=client.post("/api/research",json=body,headers=headers)
            assert first.status_code==202
            job=first.json()["job_id"];assert wait(client,headers,job)["result"]==result
            assert client.post("/api/research",json=body,headers=headers).json()==first.json()
            assert client.post("/api/research",json={**body,"query":"Other"},headers=headers).status_code==409
            other={"X-Session-Token":client.post("/api/session").json()["token"]}
            assert client.get("/api/jobs/"+job,headers=other).status_code==404
            assert client.get("/api/requests/q1",headers=other).status_code==404
            provider.assert_called_once()
