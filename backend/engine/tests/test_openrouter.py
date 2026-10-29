from tests.fixtures import wire_payload
"""Offline primary/fallback routing and strict response contracts; no live calls."""
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import httpx
from google.genai import errors
from fastapi.testclient import TestClient
import time
import os
import main

import ai_service as service
import openrouter_service as router
from request_control import BudgetExceeded, RequestBudget, SessionSubmission
from tests.fixtures import SOURCE, payload, response
from tests.test_semantic_review import scripted_review, claims


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        enabled=patch.object(service,"OPENROUTER_FALLBACK_ENABLED",True)
        enabled.start();self.addCleanup(enabled.stop)
        self.clock=[0.0];self.requests=[];self.client_options=[]
        self.budget=RequestBudget(clock=lambda:self.clock[0])
        self.keys={"GEMINI_API_KEY":"offline-gemini-placeholder", "OPENROUTER_API_KEY":"offline-openrouter-placeholder"}
        for target,name,value in ((service.os,"environ",self.keys),(service,"REQUEST_BUDGET",self.budget)):
            item=patch.object(target,name,value);item.start();self.addCleanup(item.stop)
        item=patch.object(service,"sleep",side_effect=lambda delay:self.clock.__setitem__(0,self.clock[0]+delay))
        item.start();self.addCleanup(item.stop)
        item=patch.object(service.genai,"Client");self.gemini_factory=item.start();self.addCleanup(item.stop)
        self.gemini=self.gemini_factory.return_value.__enter__.return_value.models.generate_content
        self.gemini.side_effect=errors.APIError(503,{"error":{"message":"PRIVATE primary failure"}})
        self.outputs=self.pair()
        self.router_failure=None;self.on_router_request=None
        self.real_client=httpx.Client
        item=patch.object(router.httpx,"Client",side_effect=self.client)
        self.router_factory=item.start();self.addCleanup(item.stop)

    def pair(self, data=None, source=SOURCE, accepted=None):
        data=payload() if data is None else data
        checked=service.check_evidence(service.ProviderAnalysis.model_validate(data),source,
            source_type="user_provided",source_url=None,model=router.OPENROUTER_MODEL)
        accepted=set(service.review_candidates(checked)) if accepted is None else accepted
        review=scripted_review(checked,source,accepted)
        return [json.dumps(wire_payload(data),ensure_ascii=False),review.model_dump_json()]

    def client(self, **options):
        self.client_options.append(options)
        def respond(request):
            body=json.loads(request.content)
            self.requests.append((body,self.clock[0]))
            if self.on_router_request:self.on_router_request()
            self.assertEqual(str(request.url),router.ENDPOINT)
            self.assertEqual(request.headers["Authorization"],"Bearer offline-openrouter-placeholder")
            if self.router_failure:raise self.router_failure
            value=self.outputs[len(self.requests)-1]
            if isinstance(value,httpx.Response):return value
            return httpx.Response(200,json={"model":router.OPENROUTER_MODEL,
                "choices":[{"finish_reason":"stop","message":{"role":"assistant","content":value}}]})
        return self.real_client(transport=httpx.MockTransport(respond),**options)

    def test_primary_success_never_reads_or_calls_optional_provider(self):
        checked=service.check_evidence(service.ProviderAnalysis.model_validate(payload()),SOURCE,
            source_type="user_provided",source_url=None,model=service.DEFAULT_MODEL)
        review=scripted_review(checked,SOURCE,set(service.review_candidates(checked)))
        self.gemini.side_effect=[response(payload()),response(review.model_dump())]
        with patch.object(service,"_openrouter_key") as key:
            result=service.analyze_instructions(SOURCE)
        key.assert_not_called();self.router_factory.assert_not_called()
        self.assertEqual(result.model,service.DEFAULT_MODEL)
        self.assertTrue(result.semantic_review_complete)
        self.assertEqual(self.gemini.call_count,2)

    def test_configured_service_failure_uses_strict_complete_fallback_pair(self):
        result=service.analyze_instructions(SOURCE,question="Public question",source_scope="Limited public scope",output_language="en")
        self.assertEqual(self.gemini.call_count,1)
        self.assertEqual(len(self.requests),2)
        self.assertEqual(result.model,router.OPENROUTER_MODEL)
        self.assertTrue(result.semantic_review_complete)
        self.assertTrue(all(c.semantic_status=="supported" for c in claims(result)))
        first,second=[value for value,_ in self.requests]
        for request in (first,second):
            self.assertEqual(request["model"],router.OPENROUTER_MODEL)
            self.assertEqual(request["provider"],{"require_parameters":True,"allow_fallbacks":False,
                "max_price":{"prompt":0,"completion":0,"request":0}})
            self.assertTrue(request["response_format"]["json_schema"]["strict"])
            self.assertNotIn("models",request)
            self.assertNotIn("plugins",request)
            self.assertNotIn("offline-openrouter-placeholder",json.dumps(request))
        self.assertEqual(first["response_format"]["json_schema"]["schema"],service.QuoteFirstAnalysis.model_json_schema())
        self.assertEqual(second["response_format"]["json_schema"]["schema"],service.SemanticReview.model_json_schema())
        envelope=json.loads(first["messages"][1]["content"])
        self.assertEqual(envelope["source_text"],SOURCE)
        self.assertEqual(envelope["question"],"Public question")
        self.assertEqual(json.loads(second["messages"][1]["content"])["source_text"],SOURCE)
        self.assertEqual([t for _,t in self.requests],[0,2])
        self.assertTrue(all(o=={"timeout":60.0,"follow_redirects":False,"trust_env":False} for o in self.client_options))

    def test_unconfigured_blank_and_example_keys_keep_original_error(self):
        for key in (None,"", "  ","replace-with-your-own-key-locally"):
            with self.subTest(key=key):
                self.keys["OPENROUTER_API_KEY"]=key
                self.clock[0]+=60
                with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
                self.assertEqual(caught.exception.code,"service_busy")
        self.router_factory.assert_not_called()

    def test_invalid_optional_key_fails_safely_without_transport(self):
        self.keys["OPENROUTER_API_KEY"]=42
        with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
        self.assertEqual(caught.exception.code,"configuration")
        self.router_factory.assert_not_called()

    def test_transient_primary_statuses_are_eligible_once(self):
        for status in (408,429,500,502,503,504,507):
            with self.subTest(status=status):
                self.clock[0]+=60;self.requests.clear()
                self.gemini.side_effect=errors.APIError(status,{"error":{"message":"PRIVATE"}})
                result=service.analyze_instructions(SOURCE)
                self.assertTrue(result.semantic_review_complete)
                self.assertEqual(len(self.requests),2)

    def test_primary_network_and_timeout_are_eligible(self):
        for failure in (httpx.ConnectError("PRIVATE"),httpx.ReadTimeout("PRIVATE")):
            self.clock[0]+=60;self.requests.clear();self.gemini.side_effect=failure
            self.assertTrue(service.analyze_instructions(SOURCE).semantic_review_complete)
            self.assertEqual(len(self.requests),2)

    def test_permanent_primary_errors_and_malformed_generation_do_not_fallback(self):
        for status in (400,401,403,404):
            self.clock[0]+=60
            self.gemini.side_effect=errors.APIError(status,{"error":{"message":"PRIVATE"}})
            with self.assertRaises(service.AnalysisError):service.analyze_instructions(SOURCE)
        self.clock[0]+=60;self.gemini.side_effect=None;self.gemini.return_value=response({"bad":"schema"})
        with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
        self.assertEqual(caught.exception.code,"malformed_response")
        self.router_factory.assert_not_called()

    def test_input_provenance_pause_missing_key_and_local_guards_do_not_fallback(self):
        for source,options in (("",{}),("x"*50001,{}),(SOURCE,{"source_type":"verified_guide"}),(SOURCE,{"output_language":"fr"})):
            with self.assertRaises(service.AnalysisError):service.analyze_instructions(source,**options)
        with patch.object(service,"ANALYSIS_ENABLED",False),self.assertRaises(service.AnalysisError):
            service.analyze_instructions(SOURCE)
        with patch.dict(self.keys,{"GEMINI_API_KEY":""}),self.assertRaises(service.AnalysisError):
            service.analyze_instructions(SOURCE)
        for code in ("local_rate_limit","local_token_limit"):
            with patch.object(self.budget,"reserve",side_effect=BudgetExceeded(code,"Local guard")),self.assertRaises(service.AnalysisError):
                service.analyze_instructions(SOURCE)
        self.router_factory.assert_not_called();self.gemini_factory.assert_not_called()

    def test_malformed_primary_review_never_falls_back(self):
        self.gemini.side_effect=[response(payload()),response({"decisions":[],"evidence":[]})]
        result=service.analyze_instructions(SOURCE)
        self.assertEqual(result.review_mode,"deterministic_only")
        self.assertEqual(result.review_failure,"malformed_response")
        self.assertEqual(self.gemini.call_count,2)
        self.router_factory.assert_not_called()

    def test_image_extraction_failure_stays_gemini_only_even_when_fallback_configured(self):
        import ocr_service
        from tests.test_gemini_ocr import image_bytes
        with self.assertRaises(service.AnalysisError) as caught:
            ocr_service.extract_image_text(image_bytes(),"public.png")
        self.assertEqual(caught.exception.code,"service_busy")
        self.assertEqual(self.gemini.call_count,1)
        self.router_factory.assert_not_called()

    def test_fallback_local_admission_guard_blocks_dispatch_without_loop(self):
        reserve=self.budget.reserve
        def admit(scope,tokens,**kwargs):
            if scope[1]==router.OPENROUTER_MODEL:
                raise BudgetExceeded("local_token_limit","Local guard")
            return reserve(scope,tokens,**kwargs)
        with patch.object(self.budget,"reserve",side_effect=admit),self.assertRaises(service.AnalysisError) as caught:
            service.analyze_instructions(SOURCE)
        self.assertEqual(caught.exception.code,"local_token_limit")
        self.assertEqual(self.gemini.call_count,1)
        self.router_factory.assert_not_called()

    def test_failed_primary_review_keeps_locally_checked_draft_without_secondary_generation(self):
        self.gemini.side_effect=[response(payload()),errors.APIError(503,{"error":{"message":"PRIVATE"}})]
        result=service.analyze_instructions(SOURCE)
        self.assertFalse(result.semantic_review_complete)
        self.assertEqual(result.model,service.DEFAULT_MODEL)
        self.assertEqual(self.gemini.call_count,2)
        self.assertEqual(len(self.requests),0)
        self.assertEqual(sum(len(u.recent) for u in self.budget._usage.values()),2)
        self.assertEqual(self.clock[0],2)

    def test_withheld_primary_claims_do_not_trigger_a_second_provider(self):
        checked=service.check_evidence(service.ProviderAnalysis.model_validate(payload()),SOURCE,
            source_type="user_provided",source_url=None,model=service.DEFAULT_MODEL)
        review=scripted_review(checked,SOURCE,set())
        self.gemini.side_effect=[response(payload()),response(review.model_dump())]
        result=service.analyze_instructions(SOURCE)
        self.assertTrue(all(c.semantic_status=="withheld" for c in claims(result)))
        self.router_factory.assert_not_called()

    def test_malformed_secondary_generation_never_starts_review(self):
        for bad in ('not JSON','```json {} ```','{"extra":"field"}'):
            self.clock[0]+=60;self.requests.clear();self.outputs=[bad]
            with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
            self.assertEqual(caught.exception.code,"malformed_response")
            self.assertEqual(len(self.requests),1)

    def test_missing_review_decisions_return_locally_admitted_unreviewed_draft(self):
        review=json.loads(self.outputs[1]);review["decisions"]=[]
        self.outputs[1]=json.dumps(review)
        result=service.analyze_instructions(SOURCE)
        self.assertEqual(result.review_mode,"deterministic_only")
        self.assertEqual(result.review_failure,"malformed_response")
        self.assertEqual(len(self.requests),2)

    def test_invalid_review_quotes_cannot_support_actionable_claims(self):
        review=json.loads(self.outputs[1]);review["evidence"][0]["excerpt"]="fabricated non-source excerpt"
        self.outputs[1]=json.dumps(review)
        result=service.analyze_instructions(SOURCE)
        self.assertTrue(all(c.semantic_status=="withheld" for c in claims(result)))
        self.assertEqual(len(self.requests),2)

    def test_secondary_unmatched_generation_quote_remains_withheld_despite_review_approval(self):
        data=payload();data["evidence"][0]["excerpt"]="invented non-source excerpt"
        self.outputs=self.pair(data)
        result=service.analyze_instructions(SOURCE)
        self.assertFalse(result.evidence[0].excerpt_found)
        self.assertEqual(result.steps[0].semantic_status,"withheld")

    def test_secondary_review_admitted_documents_survive_removed_scope_hold(self):
        case=json.loads((Path(__file__).parent/"data/epassport_gemini35_corrected_review.json").read_text(encoding="utf-8"))
        self.outputs=[json.dumps(wire_payload(case["provider_output"])),json.dumps(case["semantic_review"])]
        result=service.analyze_instructions(case["source"])
        self.assertTrue(result.semantic_review_complete)
        self.assertEqual(result.documents[0].semantic_status,"supported")
        self.assertEqual(result.documents[2].semantic_status,"supported")
        self.assertEqual(sum(c.semantic_status=="supported" for c in claims(result)),35)
        self.assertEqual(sum(c.semantic_status=="withheld" for c in claims(result)),2)
        self.assertEqual(result.model,router.OPENROUTER_MODEL)

    def test_router_failures_never_loop_or_retry_and_are_sanitized(self):
        for status in (302,400,401,402,403,404,429,503):
            self.clock[0]+=60;self.requests.clear()
            self.outputs=[httpx.Response(status,json={"error":{"message":"PRIVATE source and key"}})]
            with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
            self.assertNotIn("PRIVATE",str(caught.exception))
            self.assertIsNone(caught.exception.diagnostics)
            self.assertEqual(len(self.requests),1)

    def test_router_timeout_no_retry(self):
        self.router_failure=httpx.ReadTimeout("PRIVATE")
        with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
        self.assertEqual(caught.exception.code,"timeout")
        self.assertEqual(len(self.requests),1)

    def test_error_envelopes_and_incomplete_responses_are_not_accepted(self):
        envelopes=[{"error":{"code":503,"message":"PRIVATE"}},[],{},
            {"model":router.OPENROUTER_MODEL,"choices":[{"finish_reason":"length","message":{"role":"assistant","content":"{}"}}]},
            {"model":router.OPENROUTER_MODEL,"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"{}","refusal":"PRIVATE"}}]},
            {"model":"paid/other-model","choices":[]},
            {"model":router.OPENROUTER_MODEL,"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":[]}}]}]
        for envelope in envelopes:
            self.clock[0]+=60;self.requests.clear();self.outputs=[httpx.Response(200,json=envelope)]
            with self.assertRaises(service.AnalysisError):service.analyze_instructions(SOURCE)
            self.assertEqual(len(self.requests),1)

    def test_router_review_failure_returns_labelled_locally_admitted_draft(self):
        self.outputs[1]=httpx.Response(503,json={"error":{"message":"PRIVATE"}})
        result=service.analyze_instructions(SOURCE)
        self.assertEqual(result.review_mode,"deterministic_only")
        self.assertFalse(result.semantic_review_complete)
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.gemini.call_count,1)

    def test_secondary_review_quota_and_timeout_keep_only_explicitly_degraded_guidance(self):
        failures=(httpx.Response(429,json={"error":{"message":"PRIVATE"}}),
                  httpx.ReadTimeout("PRIVATE"))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                self.clock[0]+=60;self.requests.clear();self.outputs=self.pair()
                if isinstance(failure,httpx.Response):
                    self.outputs[1]=failure
                    result=service.analyze_instructions(SOURCE)
                else:
                    def fail_review():
                        if len(self.requests)==2:raise failure
                    self.on_router_request=fail_review
                    try:result=service.analyze_instructions(SOURCE)
                    finally:self.on_router_request=None
                exported=main.public_result(result)
                self.assertEqual(exported["review_mode"],"deterministic_only")
                self.assertFalse(exported["semantic_review_complete"])
                self.assertTrue(exported["has_guidance"])
                self.assertEqual(len(self.requests),2)
                self.assertTrue(all(e.excerpt_found for e in result.evidence))

    def test_owned_api_job_replays_and_reads_keep_one_complete_fallback_pair(self):
        with TestClient(main.app) as client:
            headers={"X-Session-Token":client.post("/api/session").json()["token"]}
            body={"text":SOURCE,"reviewed":True,"kind":"text","revision":"fallback-api","request_id":"fallback-request"}
            first=client.post("/api/analysis",headers=headers,json=body)
            self.assertEqual(first.status_code,202)
            job=first.json()["job_id"]
            second=client.post("/api/analysis",headers=headers,json=body)
            self.assertEqual(second.json()["job_id"],job)
            for _ in range(100):
                snapshot=client.get(f"/api/jobs/{job}",headers=headers).json()
                if snapshot["status"] in {"succeeded","failed"}:break
                time.sleep(.01)
            self.assertEqual(snapshot["status"],"succeeded")
            self.assertTrue(snapshot["result"]["semantic_review_complete"])
            self.assertEqual(client.get(f"/api/jobs/{job}",headers=headers).json(),snapshot)
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.gemini.call_count,1)

class ProductionFallbackTests(unittest.TestCase):
    def test_explicit_environment_key_opts_into_bounded_fallback(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "offline-placeholder"},clear=True):
            self.assertFalse(service.OPENROUTER_FALLBACK_ENABLED)
            self.assertEqual(service._openrouter_key().get_secret_value(),"offline-placeholder")
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(service._openrouter_key())
