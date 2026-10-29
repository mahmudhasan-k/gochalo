"""Recorded provider failures and configuration decision; no live provider calls."""
import hashlib
import json
import os
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

import httpx
from google.genai import types

import ai_service as service
import openrouter_service
from request_control import RequestBudget

ROOT=Path(__file__).resolve().parents[1]
RECORD=json.loads((ROOT/"tests/data/gemini38_evaluation.json").read_text(encoding="utf-8"))


class Gemini38EvaluationTests(unittest.TestCase):
    def test_sources_and_nine_independent_p1_criteria_are_unchanged(self):
        expected=json.loads((ROOT/"tests/data/p1_scope.json").read_text(encoding="utf-8"))["expected"]
        for case in RECORD["cases"].values():
            source=json.loads((ROOT/"tests/data"/case["source_fixture"]).read_text(encoding="utf-8"))["source"]
            self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),case["source_sha256"])
        criteria=RECORD["cases"]["corrected_p1"]["independent_assessment"]["criteria"]
        self.assertEqual([c["criterion"] for c in criteria],expected)
        self.assertEqual(len(criteria),9)
        self.assertTrue(all(c["outcome"]=="not_assessed_no_output" for c in criteria))

    def test_each_distinct_case_was_attempted_once_without_review_or_retry(self):
        self.assertEqual(RECORD["actual_requests"],3)
        self.assertEqual(RECORD["actual_inference_requests"],2)
        self.assertEqual(RECORD["actual_metadata_requests"],1)
        self.assertLessEqual(RECORD["actual_requests"],RECORD["authorization_limit"])
        self.assertEqual([x["phase"] for x in RECORD["attempts"]],
            ["corrected_p1:generation","official_epassport:generation","model_metadata"])
        self.assertEqual([x["http_status"] for x in RECORD["attempts"]],[504,503,200])
        self.assertTrue(all(x["elapsed_seconds"]>0 for x in RECORD["attempts"]))
        self.assertTrue(all(c["review"]["requests"]==0 for c in RECORD["cases"].values()))
        for key in ("jina_requests","openrouter_requests","retry_requests","billing_calls"):
            self.assertEqual(RECORD["network_boundaries"][key],0)

    def test_no_output_or_usage_is_not_misreported_as_semantic_success_or_zero_tokens(self):
        for case in RECORD["cases"].values():
            self.assertIsNone(case["generation"]["raw_provider_text"])
            self.assertIsNone(case["generation"]["schema_valid"])
            self.assertIsNone(case["generation"]["usage"])
            self.assertEqual(case["independent_assessment"]["outcome"],"not_assessed_no_output")
        self.assertTrue(RECORD["free_tier"]["published_standard_tier_available"])
        self.assertIn("unconfirmed",RECORD["free_tier"]["existing_project_availability"])

    def test_authenticated_metadata_confirms_visibility_but_not_free_inference(self):
        lookup=RECORD["metadata_lookup"]
        self.assertEqual(lookup["http_status"],200)
        self.assertFalse(lookup["inference_request"])
        self.assertEqual(lookup["metadata"]["name"],"models/gemini-3.8-flash")
        self.assertIn("generateContent",lookup["metadata"]["supported_actions"])
        self.assertIn("unconfirmed",RECORD["free_tier"]["existing_project_availability"])

    def test_primary_template_and_optional_fallback_remain_configured_as_before(self):
        template=dict(line.split("=",1) for line in (ROOT.parents[1]/".env.example").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#") and "=" in line)
        self.assertEqual(service.DEFAULT_MODEL,"gemini-3.5-flash-lite")
        self.assertEqual(template["GEMINI_MODEL"],service.DEFAULT_MODEL)
        self.assertEqual(RECORD["selection"]["primary"],service.DEFAULT_MODEL)
        self.assertEqual(openrouter_service.OPENROUTER_MODEL,"openai/gpt-oss-120b:free")
        self.assertNotIn("qwen",openrouter_service.OPENROUTER_MODEL.lower())
        self.assertEqual(template["OPENROUTER_API_KEY"],"")

    def test_installed_sdk_serializes_38_schema_and_maps_recorded_errors_without_retry(self):
        real_client=service.genai.Client
        for attempt in (a for a in RECORD["attempts"] if a["phase"].endswith(":generation")):
            requests=[]
            def respond(request):
                requests.append(json.loads(request.content))
                self.assertEqual(request.url.path,"/v1beta/models/gemini-3.8-flash:generateContent")
                return httpx.Response(attempt["http_status"],json={"error":{
                    "code":attempt["http_status"],"message":"Offline recorded provider failure"}})
            def client(**options):
                self.assertEqual(options["http_options"].timeout,60000)
                self.assertEqual(options["http_options"].retry_options.attempts,1)
                return real_client(vertexai=False,api_key="offline-placeholder",http_options=types.HttpOptions(
                    api_version=service.API_VERSION,retry_options=types.HttpRetryOptions(attempts=1),
                    client_args={"transport":httpx.MockTransport(respond)}))
            with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder","GEMINI_MODEL":"gemini-3.8-flash"}), \
                 patch.object(service.genai,"Client",side_effect=client), \
                 patch.object(service,"REQUEST_BUDGET",RequestBudget()), \
                 patch.object(service.openrouter_service,"generate_json") as fallback:
                with self.assertRaises(service.AnalysisError) as caught:
                    service._analyze_gemini("Public synthetic test instructions.")
                self.assertEqual(caught.exception.code,"timeout" if attempt["http_status"]==504 else "service_busy")
                fallback.assert_not_called()
            self.assertEqual(len(requests),1)
            self.assertEqual(requests[0]["generationConfig"]["responseJsonSchema"],service.strip_grammar_bounds(service.QuoteFirstAnalysis.model_json_schema()))
