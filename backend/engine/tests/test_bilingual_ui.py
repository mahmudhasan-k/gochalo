"""Bilingual grounding contracts; React presentation tests are Bilingual.test.tsx."""
import os,unittest
from unittest.mock import patch
import ai_service as service
from examples import load_example
from prompts import build_system_prompt
from tests.fixtures import SOURCE,payload,response

def english_payload():
    data = payload()
    data["explanation"][0]["text"] = "You can apply online."
    data["steps"][0]["text"] = "Apply online."
    data["documents"][0]["text"] = "Provide a copy of your birth registration."
    return data


def checked(data=None, *, source=SOURCE, language="en"):
    return service.check_evidence(
        service.ProviderAnalysis.model_validate(data or english_payload()), source,
        source_type="user_provided", source_url=None, model=service.DEFAULT_MODEL,
        output_language=language,
    )


@patch("ai_service.ANALYSIS_ENABLED",True)
@patch("ai_service.review_semantics",lambda result,*args,**kwargs:result)
@patch("ai_service.sleep",lambda delay:None)
class BilingualGroundingTests(unittest.TestCase):
    def test_normalized_match_displays_original_source_punctuation(self):
        data = payload()
        data["evidence"][0]["excerpt"] = "অনলাইনে আবেদন করুন。"
        original = SOURCE.replace("অনলাইনে আবেদন", "অনলাইনে\n  আবেদন")
        result = checked(data, source=original)
        self.assertTrue(result.evidence[0].excerpt_found)
        self.assertEqual(result.evidence[0].excerpt, "অনলাইনে\n  আবেদন করুন।")
        self.assertIn(result.evidence[0].excerpt, original)

    def test_static_english_example_keeps_saved_source_and_evidence(self):
        bn, en = load_example(), load_example(output_language="en")
        self.assertIsNotNone(en)
        self.assertEqual(bn[0].model_dump(), en[0].model_dump())
        self.assertEqual(bn[1].evidence, en[1].evidence)
        self.assertTrue(all(c.evidence_status == "quotation_matched" for c in en[1].explanation + en[1].steps))
        self.assertTrue(en[0].fictional)
        self.assertIsNone(en[1].source_url)
        self.assertIn("students", en[1].fees_and_deadlines.fees[0].text)

    def test_english_missing_notices_deduplicate_without_hiding_conditions(self):
        data = english_payload()
        data["unknowns"] = [
            {"kind": "missing", "text": "Fees: This information is not in the supplied source.", "evidence_ids": []},
            {"kind": "missing", "text": "Fees: This information is not in the supplied source.", "evidence_ids": []},
            {"kind": "missing", "text": "Fees: Student fees are not specified.", "evidence_ids": []},
        ]
        result = checked(data)
        self.assertEqual(len(result.unknowns), 3)  # Fee default, student condition, deadline default.
        self.assertTrue(any("Student" in x.text for x in result.unknowns))
        self.assertFalse(result.fees_and_deadlines.fees)

    def test_english_conflicting_category_is_not_called_missing(self):
        data = english_payload()
        data["unknowns"] = [{"kind": "contradiction", "text": "Fees: Two amounts conflict.", "evidence_ids": ["e1", "e2"]}]
        result = checked(data)
        self.assertTrue(all(x.evidence_status == "contradictory" for x in result.explanation + result.steps + result.documents))
        self.assertFalse(any(x.kind == "missing" and x.text.startswith("Fees:") for x in result.unknowns))

    def test_english_claims_keep_numeric_and_fabricated_quote_checks(self):
        data = english_payload()
        data["explanation"][0]["text"] = "Pay 500 taka."
        data["evidence"][1]["excerpt"] = "A fabricated government quotation."
        result = checked(data)
        self.assertEqual(result.explanation[0].evidence_status, "unsupported")
        self.assertEqual(result.documents[0].evidence_status, "unsupported")
        self.assertTrue(any(x.text.startswith("Unsupported AI claim") for x in result.unknowns))
        self.assertFalse(result.evidence[1].excerpt_found)

    def test_english_age_claim_cannot_bypass_existing_bangla_conflict_check(self):
        source = "সেবা A — নিবন্ধন: কেবল ১৮ বছর বা বেশি বয়সীরা আবেদন করতে পারবেন। কেবল ১৮ বছরের কম বয়সীরা আবেদন করতে পারবেন।"
        data = english_payload()
        data["explanation"][0].update(text="Only applicants aged ১৮ or above are eligible.", evidence_ids=["e1"])
        data["steps"] = []
        data["documents"] = []
        data["evidence"] = [
            {"id": "e1", "excerpt": "কেবল ১৮ বছর বা বেশি বয়সীরা আবেদন করতে পারবেন।"},
            {"id": "e2", "excerpt": "কেবল ১৮ বছরের কম বয়সীরা আবেদন করতে পারবেন।"},
        ]
        result = checked(data, source=source)
        self.assertEqual(result.explanation[0].evidence_status, "contradictory")
        conflict = next(x for x in result.unknowns if x.text.startswith("Eligibility:"))
        self.assertEqual(conflict.evidence_ids, ["e1", "e2"])
        self.assertIn(data["evidence"][0]["excerpt"], conflict.text)

    def test_selected_prompt_and_estimate_are_used_in_one_mocked_request(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-placeholder"}), \
             patch.object(service, "REQUEST_BUDGET") as budget, \
             patch.object(service.genai, "Client") as factory:
            generate = factory.return_value.__enter__.return_value.models.generate_content
            generate.return_value = response(english_payload())
            result = service.analyze_instructions(SOURCE, output_language="en")
            generate.assert_called_once()
            prompt = generate.call_args.kwargs["config"].system_instruction
            self.assertEqual(prompt, build_system_prompt("en"))
            self.assertIn("must be English", prompt)
            self.assertIn("UNTRUSTED SOURCE MATERIAL", prompt)
            self.assertNotIn("must be Bangla", prompt)
            self.assertEqual(result.evidence[0].excerpt, payload()["evidence"][0]["excerpt"])
            budget.reserve.assert_called_once()
            self.assertEqual(budget.reserve.call_args.args[1], service.estimate_input_tokens(generate.call_args.kwargs["contents"], "en"))

    def test_invalid_language_rejected_before_provider_or_secrets(self):
        with patch.object(service.genai, "Client") as client, patch.object(service, "load_settings") as settings:
            with self.assertRaises(service.AnalysisError):
                service.analyze_instructions(SOURCE, output_language="untrusted")
            client.assert_not_called()
            settings.assert_not_called()
