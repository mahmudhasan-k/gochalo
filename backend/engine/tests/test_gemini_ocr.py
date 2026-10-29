from tests.fixtures import wire_payload
"""Image extraction over the installed SDK with offline HTTP transports only."""
import json
import os
from io import BytesIO
from PIL import Image
from unittest.mock import patch
import unittest

import httpx
from google.genai import types

import ai_service as service
import ocr_service as ocr
from request_control import RequestBudget, SessionSubmission
def image_bytes():
    output=BytesIO()
    Image.new("RGB",(80,40),"white").save(output,format="PNG")
    return output.getvalue()


class GeminiOCRTests(unittest.TestCase):
    def invoke(self, text=None, *, status=200, finish="STOP", raw=None, failure=None):
        self.requests=[]
        self.clock=[0.0]
        self.budget=RequestBudget(clock=lambda:self.clock[0])
        real_client=service.genai.Client
        def respond(request):
            self.requests.append(json.loads(request.content))
            if failure:raise failure
            if status!=200:
                return httpx.Response(status,json={"error":{"code":status,"message":"PRIVATE source/key"}})
            body=raw if raw is not None else json.dumps({"text":text},ensure_ascii=False)
            return httpx.Response(200,json={"candidates":[] if finish is None else [{"content":{"role":"model","parts":[{"text":body}]},"finishReason":finish}]})
        def client(**kwargs):
            self.assertEqual(kwargs["http_options"].retry_options.attempts,1)
            self.assertEqual(kwargs["http_options"].timeout,60_000)
            return real_client(vertexai=False,api_key="offline-test-placeholder",http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"transport":httpx.MockTransport(respond)}))
        with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-test-placeholder","LOCAL_OCR_ENABLED":"0"}), \
             patch.object(service,"REQUEST_BUDGET",self.budget), \
             patch.object(service.genai,"Client",side_effect=client), \
             patch.object(service,"analyze_instructions") as analysis:
            try:return ocr.extract_image_text(image_bytes(),"public.png",session=SessionSubmission())
            finally:analysis.assert_not_called()

    def test_exact_bilingual_text_inline_image_and_strict_schema(self):
        text="৫ কপি / 5 copies\nপরিবর্তনযোগ্য নয়। NID অথবা BRC।\nFee: 100; deadline: 2026-11-05."
        self.assertEqual(self.invoke(text),text)
        request=self.requests[0]
        self.assertEqual(request["contents"][0]["parts"][0]["inlineData"]["mime_type"],"image/png")
        self.assertEqual(request["generationConfig"]["responseJsonSchema"],ocr.strip_grammar_bounds(ocr.ImageTranscription.model_json_schema()))
        self.assertEqual(len(self.requests),1)
        self.assertEqual(sum(len(u.recent) for u in self.budget._usage.values()),1)
        self.assertNotIn("offline-test-placeholder",json.dumps(request))

    def test_partial_unreadability_is_explicit_and_not_repaired(self):
        text="Copies: [unreadable]\nPublic notice"
        self.assertEqual(self.invoke(text),text)

    def test_empty_or_fully_unreadable_source_is_not_accepted(self):
        for text in ("", "   ", "[unreadable]"):
            with self.subTest(text=text),self.assertRaises(service.AnalysisError) as caught:
                self.invoke(text)
            self.assertEqual(caught.exception.code,"image_empty")
            self.assertEqual(len(self.requests),1)

    def test_malformed_extra_fields_wrong_types_and_oversized_text_rejected(self):
        for raw in ("not json",'{"text":5}','{"text":"source","answer":"invented"}',json.dumps({"text":"x"*10001})):
            with self.subTest(raw=raw[:30]),self.assertRaises(service.AnalysisError) as caught:
                self.invoke(raw=raw)
            self.assertEqual(caught.exception.code,"malformed_response")
            self.assertEqual(len(self.requests),1)

    def test_truncated_response_is_rejected(self):
        for finish in ("MAX_TOKENS", "SAFETY", None):
            with self.subTest(finish=finish),self.assertRaises(service.AnalysisError) as caught:
                self.invoke("partial",finish=finish)
            self.assertEqual(caught.exception.code,"malformed_response")

    def test_provider_failures_are_sanitized_single_attempts(self):
        for status,code in ((429,"rate_limit_or_quota"),(503,"service_busy"),(403,"access_denied"),(404,"model_unavailable")):
            with self.subTest(status=status),self.assertRaises(service.AnalysisError) as caught:
                self.invoke(status=status)
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn("PRIVATE",str(caught.exception))
            self.assertEqual(len(self.requests),1)
            self.assertEqual(sum(len(u.recent) for u in self.budget._usage.values()),1)

    def test_timeout_and_network_errors_are_single_attempts(self):
        for failure,code in ((httpx.ReadTimeout("PRIVATE"),"timeout"),(httpx.ConnectError("PRIVATE"),"network_error")):
            with self.subTest(code=code),self.assertRaises(service.AnalysisError) as caught:
                self.invoke(failure=failure)
            self.assertEqual(caught.exception.code,code)
            self.assertEqual(len(self.requests),1)

    def test_invalid_image_and_missing_configuration_do_not_dispatch(self):
        with patch.object(service.genai,"Client") as client:
            with self.assertRaises(service.AnalysisError):ocr.extract_image_text(b"not image","a.png")
            with patch.dict(os.environ,{"GEMINI_API_KEY":"","LOCAL_OCR_ENABLED":"0"}),self.assertRaises(service.AnalysisError):
                ocr.extract_image_text(image_bytes(),"a.png")
        client.assert_not_called()

    def test_local_image_budget_rejection_prevents_provider_construction(self):
        from request_control import BudgetExceeded
        with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-test-placeholder","LOCAL_OCR_ENABLED":"0"}), \
             patch.object(service,"REQUEST_BUDGET") as budget,patch.object(service.genai,"Client") as client:
            budget.wait_seconds.return_value=0
            budget.reserve.side_effect=BudgetExceeded("local_token_limit","Local minute guard")
            with self.assertRaises(service.AnalysisError) as caught:
                ocr.extract_image_text(image_bytes(),"a.png")
        self.assertEqual(caught.exception.code,"local_token_limit")
        self.assertGreater(budget.reserve.call_args.args[1],258)
        client.assert_not_called()

    def test_extraction_generation_review_are_separate_and_share_cooldowns(self):
        from tests.fixtures import SOURCE,payload
        from tests.test_semantic_review import scripted_review
        requests=[];clock=[0.0];budget=RequestBudget(clock=lambda:clock[0]);session=SessionSubmission()
        checked=service.check_evidence(service.ProviderAnalysis.model_validate(payload()),SOURCE,
            source_type="user_provided",source_url=None,model=service.DEFAULT_MODEL)
        review=scripted_review(checked,SOURCE,set(service.review_candidates(checked)))
        outputs=[json.dumps({"text":SOURCE}),json.dumps(wire_payload(payload())),review.model_dump_json()]
        real_client=service.genai.Client
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200,json={"candidates":[{"content":{"role":"model","parts":[{"text":outputs[len(requests)-1]}]},"finishReason":"STOP"}]})
        def client(**kwargs):
            return real_client(vertexai=False,api_key="offline-test-placeholder",http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),client_args={"transport":httpx.MockTransport(respond)}))
        with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-test-placeholder","LOCAL_OCR_ENABLED":"0"}), \
             patch.object(service,"REQUEST_BUDGET",budget),patch.object(service.genai,"Client",side_effect=client), \
             patch.object(service,"sleep",side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)):
            extracted=ocr.extract_image_text(image_bytes(),"a.png",session=session)
            self.assertEqual(len(requests),1)
            self.assertEqual(extracted,SOURCE)
            result=service.analyze_instructions(extracted,session=session)
        self.assertTrue(result.semantic_review_complete)
        self.assertEqual(len(requests),3)
        self.assertEqual(clock[0],4)
        self.assertEqual([stamp for u in budget._usage.values() for stamp,_ in u.recent],[0,2,4])
