import copy
import unittest

import ai_service as service
from prompts import SYSTEM_PROMPT
from tests.fixtures import SOURCE, claim, misplaced_missing_notices, payload


def checked(data=None, source=SOURCE):
    return service.check_evidence(
        service.ProviderAnalysis.model_validate(payload() if data is None else data),
        source, source_type="user_provided", source_url=None, model=service.DEFAULT_MODEL,
    )


class QualityTests(unittest.TestCase):
    def test_recorded_missing_notices_become_two_unknowns_and_no_fee_facts(self):
        data = misplaced_missing_notices()
        before = copy.deepcopy(data)
        result = checked(data)
        self.assertEqual(result.fees_and_deadlines.fees, [])
        self.assertEqual(result.fees_and_deadlines.deadlines, [])
        self.assertEqual(len(result.unknowns), 2)
        self.assertTrue(all(item.kind == "missing" for item in result.unknowns))
        self.assertTrue(any(item.text.startswith("ফি:") for item in result.unknowns))
        self.assertTrue(any(item.text.startswith("সময়সীমা:") for item in result.unknowns))
        self.assertEqual(data, before)

    def test_empty_arrays_and_repeated_notices_do_not_duplicate_local_defaults(self):
        data = payload()
        data["unknowns"] = misplaced_missing_notices()["unknowns"] * 2
        result = checked(data)
        self.assertEqual(len(result.unknowns), 2)

    def test_repeated_unsupported_claims_merge_citations_without_promoting(self):
        data = payload()
        data["explanation"] = [claim("ফি ৫০০ টাকা।", ["e1"], "unsupported")]
        data["steps"] = [claim("ফি ৫০০ টাকা।", ["e2"], "unsupported")]
        result = checked(data)
        warnings = [item for item in result.unknowns if "৫০০ টাকা" in item.text]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].evidence_ids, ["e1", "e2"])
        self.assertTrue(all(item.evidence_status == "unsupported" for item in result.explanation + result.steps))

    def test_unsupported_fee_and_deadline_facts_are_flagged_not_called_missing(self):
        data = payload()
        data["fees_and_deadlines"] = {
            "fees": [claim("ফি ৫০০ টাকা।", [], "unsupported")],
            "deadlines": [claim("সময়সীমা ৭ দিন।", ["e99"])],
        }
        result = checked(data)
        self.assertEqual(result.fees_and_deadlines.fees, [])
        self.assertEqual(result.fees_and_deadlines.deadlines, [])
        self.assertEqual(len(result.unknowns), 2)
        self.assertTrue(all(item.kind == "unverified" for item in result.unknowns))
        self.assertTrue(any("৫০০ টাকা" in item.text for item in result.unknowns))
        self.assertTrue(any("৭ দিন" in item.text for item in result.unknowns))

    def test_no_fee_and_no_deadline_are_not_treated_as_absence_boilerplate(self):
        data = payload()
        source = SOURCE + " ফি নেই। কোনো সময়সীমা নেই।"
        data["evidence"] += [{"id": "e3", "excerpt": "ফি নেই।"}, {"id": "e4", "excerpt": "কোনো সময়সীমা নেই।"}]
        data["fees_and_deadlines"] = {"fees": [claim("ফি নেই।", ["e3"])], "deadlines": [claim("কোনো সময়সীমা নেই।", ["e4"])]}
        result = checked(data, source)
        self.assertEqual(len(result.fees_and_deadlines.fees), 1)
        self.assertEqual(len(result.fees_and_deadlines.deadlines), 1)
        self.assertFalse(result.unknowns)
        # The same words without source evidence must never become verified.
        result = checked(data)
        self.assertFalse(result.fees_and_deadlines.fees)
        self.assertTrue(any("সমর্থনহীন" in item.text and "ফি নেই" in item.text for item in result.unknowns))

    def test_conditional_missing_notices_are_not_collapsed_into_generic_absence(self):
        data = payload()
        data["unknowns"] = [
            {"kind": "missing", "text": "শিক্ষার্থীদের ফি সম্পর্কে তথ্য নেই।", "evidence_ids": []},
            {"kind": "missing", "text": "প্রাপ্তবয়স্কদের ফি সম্পর্কে তথ্য নেই।", "evidence_ids": []},
        ]
        result = checked(data)
        self.assertTrue(any(item.text == data["unknowns"][0]["text"] for item in result.unknowns))
        self.assertTrue(any(item.text == data["unknowns"][1]["text"] for item in result.unknowns))

    def test_misplaced_notice_with_fabricated_citation_still_flags_bad_support(self):
        data = misplaced_missing_notices()
        data["fees_and_deadlines"]["fees"][0]["evidence_ids"] = ["e99"]
        result = checked(data)
        self.assertEqual(result.fees_and_deadlines.fees, [])
        self.assertTrue(any(item.kind == "unverified" and item.evidence_ids == ["e99"] for item in result.unknowns))

    def test_absence_placeholder_cannot_be_promoted_by_source_stated_status(self):
        data = misplaced_missing_notices()
        data["fees_and_deadlines"]["fees"][0].update(status="source_stated", evidence_ids=["e1"])
        result = checked(data)
        self.assertFalse(result.fees_and_deadlines.fees)
        self.assertEqual(len(result.unknowns), 2)

    def test_warning_punctuation_dedupe_does_not_relax_evidence_matching(self):
        data = payload()
        data["unknowns"] = [
            {"kind": "unverified", "text": "আরও তথ্য দরকার।", "evidence_ids": ["e1"]},
            {"kind": "unverified", "text": "আরও   তথ্য দরকার.", "evidence_ids": ["e2"]},
        ]
        data["evidence"][0]["excerpt"] = "অনলাইনে আবেদন করুন!"
        result = checked(data)
        matching = [item for item in result.unknowns if item.text.startswith("আরও")]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].evidence_ids, ["e1", "e2"])
        self.assertFalse(result.evidence[0].excerpt_found)
        self.assertEqual(result.explanation[0].evidence_status, "unsupported")

    def test_schema_and_prompt_explain_empty_arrays_and_exclusive_unknowns(self):
        schema = service.QuoteFirstAnalysis.model_json_schema()
        self.assertEqual(set(schema["$defs"]["QuoteFeesAndDeadlines"]["properties"]),{"fees","deadlines"})
        for text in ("leave its factual array empty", "explicitly assess absence in unknowns", "Missing fees never mean free", "Matching quotes and numbers do not prove meaning"):
            self.assertIn(text,SYSTEM_PROMPT)
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
