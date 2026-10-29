"""Deterministic processor/UI tests; no claim about Gemini generation quality."""

import copy
import json
import os
import time
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import main
from tests.test_semantic_review import scripted_review

import ai_service as service
from prompts import SYSTEM_PROMPT
from tests.adversarial_fixtures import SYNTHETIC_LABEL, corpus, unknown
from tests.fixtures import claim, payload, response

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def factual_claims(result):
    return result.explanation + result.steps + result.documents + result.fees_and_deadlines.fees + result.fees_and_deadlines.deadlines


def visible_facts(result):
    return {item.text for item in factual_claims(result) if item.evidence_status == "quotation_matched"}


# Generation-only coverage; paired review and emergency hold are tested separately.
@patch("ai_service.ANALYSIS_ENABLED", True)
@patch("ai_service.review_semantics", lambda result, *args, **kwargs: result)
@patch("ai_service.sleep", lambda delay: None)
class OfflineProviderTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-placeholder"}),
            patch.object(service, "REQUEST_BUDGET"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(service.genai, "Client")
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.generate = self.factory.return_value.__enter__.return_value.models.generate_content

    def analyze(self, data, source):
        self.generate.return_value = response(copy.deepcopy(data))
        return service.analyze_instructions(source)

    def assert_case(self, case, result, source=None):
        visible = visible_facts(result)
        self.assertEqual(visible, set(case.expected_supported))
        for forbidden in case.prohibited_claims:
            self.assertNotIn(forbidden, visible)
        for kind, fragment in case.expected_unknowns:
            self.assertTrue(any(item.kind == kind and fragment in item.text for item in result.unknowns), (kind, fragment))
        evidence = {service.normalize_whitespace(item.excerpt): item for item in result.evidence}
        # Co-located wire output carries cited quotes only. Unused legacy
        # quotations are checked separately through the full legacy adapter.
        cited={ref for section in ("explanation","steps","documents") for item in case.model_response[section] for ref in item["evidence_ids"]}
        cited.update(ref for item in case.model_response["unknowns"] for ref in item["evidence_ids"])
        cited.update(ref for section in ("fees","deadlines") for item in case.model_response["fees_and_deadlines"][section] for ref in item["evidence_ids"])
        cited_quotes={e["excerpt"] for e in case.model_response["evidence"] if e["id"] in cited}
        for excerpt in case.required_evidence:
            if excerpt in cited_quotes:
                self.assertTrue(evidence[service.normalize_whitespace(excerpt)].excerpt_found)
        for excerpt in case.rejected_evidence:
            self.assertFalse(evidence[service.normalize_whitespace(excerpt)].excerpt_found)
        for item in result.evidence:
            if item.excerpt_found:
                self.assertIn(item.excerpt, case.source if source is None else source)
        self.assertEqual(result.source_type, "user_provided")
        self.assertIsNone(result.source_url)

    def test_twelve_synthetic_contracts_through_real_parser_and_mocked_provider(self):
        for case in corpus():
            with self.subTest(fixture=case.id):
                self.generate.reset_mock()
                before = copy.deepcopy(case.model_response)
                result = self.analyze(case.model_response, case.source)
                self.assert_case(case, result)
                self.assertEqual(case.model_response, before)
                self.generate.assert_called_once()
                args = self.generate.call_args.kwargs
                self.assertEqual(json.loads(args["contents"]), {"source_text": case.source})
                self.assertEqual(args["config"].system_instruction, SYSTEM_PROMPT)
                self.assertEqual(args["config"].response_json_schema, service.strip_grammar_bounds(service.QuoteFirstAnalysis.model_json_schema()))
                self.assertIsNone(args["config"].response_schema)
                self.assertEqual(args["model"], service.DEFAULT_MODEL)
                self.assertEqual(self.factory.call_args.kwargs["http_options"].retry_options.attempts, 1)
                self.assertEqual(self.factory.call_args.kwargs["http_options"].api_version, "v1beta")

    def test_whitespace_variants_preserve_exact_quote_contracts(self):
        for case in corpus():
            with self.subTest(fixture=case.id):
                source = case.source.replace(" ", "\n\t ")
                self.assert_case(case, self.analyze(case.model_response, source), source)

    def test_missing_required_fields_rejected_for_every_fixture(self):
        for case in corpus():
            for field in case.model_response:
                with self.subTest(fixture=case.id, field=field):
                    data = copy.deepcopy(case.model_response)
                    del data[field]
                    with self.assertRaises(service.AnalysisError) as caught:
                        self.analyze(data, case.source)
                    self.assertEqual(caught.exception.code, "malformed_response")

    def test_nested_schema_corruption_rejected(self):
        for case in corpus():
            mutations = []
            for path, value in (("status", "verified"), ("evidence_ids", "e1"), ("text", 5), ("unexpected", "private")):
                data = copy.deepcopy(case.model_response)
                data["explanation"][0][path] = value
                mutations.append(data)
            data = copy.deepcopy(case.model_response)
            data["fees_and_deadlines"]["fees"] = None
            mutations.append(data)
            for index, data in enumerate(mutations):
                with self.subTest(fixture=case.id, mutation=index):
                    with self.assertRaises(service.AnalysisError) as caught:
                        self.analyze(data, case.source)
                    self.assertEqual(caught.exception.code, "malformed_response")

    def test_duplicate_unknowns_merge_but_conditions_remain(self):
        case = next(item for item in corpus() if item.id == "duplicate_unknowns")
        result = self.analyze(case.model_response, case.source)
        self.assertEqual(sum(item.kind == "missing" and item.text.startswith("ফি:") for item in result.unknowns), 1)
        self.assertEqual(len(result.unknowns), 6)  # Four categories and two distinct concessions.

    def test_unverified_refs_withhold_claims_without_affecting_unrelated_facts(self):
        data = payload()
        data["unknowns"] = [unknown("unverified", "এই কাগজের প্রযোজ্যতা অনিশ্চিত।", "e2")]
        result = self.analyze(data, "অনলাইনে আবেদন করুন। আবেদনের সঙ্গে জন্মনিবন্ধনের অনুলিপি দিন।")
        self.assertEqual(result.explanation[0].evidence_status, "quotation_matched")
        self.assertEqual(result.documents[0].evidence_status, "unsupported")
        self.assertTrue(any(item.kind == "unverified" and "সমর্থনহীন" in item.text for item in result.unknowns))

    def test_missing_notice_refs_do_not_imply_dispute(self):
        case = corpus()[0]
        data = copy.deepcopy(case.model_response)
        data["unknowns"] = [unknown("missing", "যোগ্যতার বাড়তি শর্ত নেই।", "e1")]
        result = self.analyze(data, case.source)
        self.assertIn(case.expected_supported[0], visible_facts(result))

    def test_contradiction_remains_distinct_from_missing_and_unverified(self):
        case = next(item for item in corpus() if item.id == "contradictory_fees")
        data = copy.deepcopy(case.model_response)
        data["unknowns"] += [unknown("unverified", "আরও যাচাই প্রয়োজন।", "e2")]
        result = self.analyze(data, case.source)
        self.assertTrue(any(item.kind == "contradiction" and "AI দাবি" in item.text for item in result.unknowns))
        self.assertFalse(any(item.kind == "missing" and item.text.startswith("ফি:") for item in result.unknowns))

    def test_empty_arrays_with_conflict_or_uncertainty_are_not_labelled_missing(self):
        for identifier, category, field in (("contradictory_fees", "ফি", "fees"), ("conflicting_documents", "কাগজপত্র", "documents"), ("outdated_notice", "সময়সীমা", "deadlines")):
            with self.subTest(fixture=identifier):
                case = next(item for item in corpus() if item.id == identifier)
                data = copy.deepcopy(case.model_response)
                if field == "documents":
                    data["documents"] = []
                else:
                    data["fees_and_deadlines"][field] = []
                result = self.analyze(data, case.source)
                self.assertFalse(any(item.kind == "missing" and item.text.startswith(category + ":") for item in result.unknowns))
                self.assertTrue(any(item.kind in {"contradiction", "unverified"} and item.text.startswith(category + ":") for item in result.unknowns))
                other = "সময়সীমা" if category != "সময়সীমা" else "ফি"
                self.assertTrue(any(item.kind == "unverified" and item.text.startswith(other + ":") for item in result.unknowns))

    def test_numeric_literals_bangla_ascii_and_boundaries(self):
        for source_digits, claim_digits, supported in (("১০০", "100", True), ("100", "১০০", True), ("১০০০", "১০০", False), ("১০০", "১০০০", False), ("১৮", "২১", False)):
            with self.subTest(source_digits=source_digits, claim_digits=claim_digits):
                source = f"নমুনা শর্ত: {source_digits}।"
                data = payload()
                data["evidence"] = [{"id": "e1", "excerpt": source}]
                data["explanation"] = [claim(f"নমুনা শর্ত: {claim_digits}।")]
                data["documents"] = []
                result = self.analyze(data, source)
                self.assertEqual(result.explanation[0].evidence_status == "quotation_matched", supported)

    def test_numeric_guard_does_not_relax_original_quote_matching(self):
        data = payload()
        data["evidence"][0]["excerpt"] = "ফি ১০০ টাকা।"
        data["explanation"] = [claim("ফি 100 টাকা।")]
        result = self.analyze(data, "ফি 100 টাকা।")
        self.assertFalse(result.evidence[0].excerpt_found)
        self.assertEqual(result.explanation[0].evidence_status, "unsupported")

    def test_documented_semantic_gaps_when_model_fails_to_flag_uncertainty(self):
        # Characterize known failures explicitly. These assertions do NOT mean
        # the prohibited facts are correct or that adversarial safety passed.
        # No local lexical rule can safely prove these Bangla interpretations.
        for identifier, section in (("misleading_evidence", "fees"), ("multiple_services", "fees"), ("document_injection", "fees")):
            case = next(item for item in corpus() if item.id == identifier)
            data = copy.deepcopy(case.model_response)
            attack = data["fees_and_deadlines"][section][-1]
            attack["status"] = "source_stated"
            data["unknowns"] = []
            result = self.analyze(data, case.source)
            self.assertIn(attack["text"], case.prohibited_claims)
            self.assertIn(attack["text"], visible_facts(result), "Known limitation changed: review and update the quality report")


class CorpusContractTests(unittest.TestCase):
    def test_all_fixtures_are_labelled_independent_and_complete(self):
        cases = corpus()
        self.assertGreaterEqual(len(cases), 12)
        self.assertEqual(len({case.id for case in cases}), len(cases))
        self.assertEqual(len({case.category for case in cases}), 12)
        for case in cases:
            with self.subTest(fixture=case.id):
                self.assertTrue(case.synthetic)
                self.assertTrue(case.source.startswith(SYNTHETIC_LABEL))
                self.assertTrue(case.expected_unknowns)
                self.assertTrue(case.prohibited_claims)
                self.assertTrue(case.required_evidence)
                service.ProviderAnalysis.model_validate(case.model_response)
                for excerpt in case.required_evidence:
                    self.assertIn(excerpt, case.source)
                for excerpt in case.rejected_evidence:
                    self.assertNotIn(excerpt, case.source)
        first = corpus()
        first[0].model_response["unknowns"].clear()
        self.assertTrue(corpus()[0].model_response["unknowns"])


@patch("ai_service.sleep", lambda delay: None)
class AdversarialAPITests(unittest.TestCase):
    def submit(self,client,headers,source,revision):
        response=client.post("/api/analysis",headers=headers,json={"text":source,"reviewed":True,"kind":"text","revision":revision})
        self.assertEqual(response.status_code,202)
        for _ in range(200):
            snapshot=client.get("/api/jobs/"+response.json()["job_id"],headers=headers).json()
            if snapshot["status"] in {"succeeded","failed"}:return snapshot
            time.sleep(.005)
        self.fail("Adversarial fixture job did not finish")

    def test_entire_corpus_uses_real_parser_review_filter_and_public_api(self):
        # Review decisions are a scripted oracle, never evidence of model accuracy.
        with TestClient(main.app) as client,patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder"}),patch.object(service,"REQUEST_BUDGET"),patch.object(service.genai,"Client") as factory:
            headers={"X-Session-Token":client.post("/api/session").json()["token"]}
            generate=factory.return_value.__enter__.return_value.models.generate_content
            for case in corpus():
                with self.subTest(fixture=case.id):
                    generate.reset_mock();generate.return_value=response(copy.deepcopy(case.model_response))
                    def review(result,source,**kwargs):
                        accepted={key for key,value in service.review_candidates(result).items() if value.text in case.expected_supported}
                        return service.apply_semantic_review(result,source,scripted_review(result,source,accepted))
                    with patch.object(service,"review_semantics",side_effect=review):
                        snapshot=self.submit(client,headers,case.source,case.id)
                    self.assertEqual(snapshot["status"],"succeeded")
                    public=snapshot["result"]
                    facts={claim["text"] for section in public["sections"].values() for claim in section}
                    for forbidden in case.prohibited_claims:self.assertNotIn(forbidden,facts)
                    self.assertEqual(facts,set(case.expected_supported))
                    self.assertTrue(public["semantic_review_complete"])
                    generate.assert_called_once()

    def test_parse_failures_expose_no_result_and_saved_example_stays_provider_free(self):
        case=next(item for item in corpus() if item.id=="document_injection")
        malformed=copy.deepcopy(case.model_response);del malformed["evidence"]
        with TestClient(main.app) as client,patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder"}),patch.object(service,"REQUEST_BUDGET"),patch.object(service.genai,"Client") as factory:
            headers={"X-Session-Token":client.post("/api/session").json()["token"]}
            generate=factory.return_value.__enter__.return_value.models.generate_content
            generate.side_effect=[response(text="PRIVATE_SOURCE not JSON"),response(malformed)]
            for index in range(2):
                snapshot=self.submit(client,headers,case.source,str(index))
                self.assertEqual(snapshot["status"],"failed")
                self.assertEqual(snapshot["error"],"malformed_response")
                self.assertIsNone(snapshot["result"])
                self.assertNotIn("PRIVATE",str(snapshot))
            saved=client.get("/api/example").json()
            self.assertTrue(saved["fictional"])
            self.assertEqual(generate.call_count,2)
