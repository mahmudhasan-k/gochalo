"""Offline prompt contracts and scripted responses, not Gemini quality tests."""

import json
import os
import unittest
from unittest.mock import patch

import ai_service as service
from prompts import build_system_prompt
from tests.fixtures import claim, response

# Authentic acceptance passage, retrieved 2026-10-21 from:
# https://www.epassport.gov.bd/instructions/instructions
PASSPORT_SOURCE = "৫। অপ্রাপ্ত বয়স্ক (১৮ বছরের কম) আবেদনকারী যার জাতীয় পরিচয়পত্র (NID) নাই, তার পিতা অথবা মাতার জাতীয় পরিচয়পত্র (NID) নম্বর অবশ্যই উল্লেখ করতে হবে।"

# Deliberately synthetic contrast: an explicit document requirement with both
# an applicability condition and an exception. This is not government guidance.
DOCUMENT_SOURCE = "বিদেশ থেকে পাসপোর্ট নবায়নের আবেদন করলে মূল জাতীয় পরিচয়পত্র অথবা মূল জন্মনিবন্ধন সনদ জমা দিন, তবে আগে জমা দিয়ে থাকলে আবার দিতে হবে না।"


# Generation-only coverage; paired review and emergency hold are tested separately.
@patch("ai_service.ANALYSIS_ENABLED", True)
@patch("ai_service.review_semantics", lambda result, *args, **kwargs: result)
class ConditionalGuidanceTests(unittest.TestCase):
    def test_both_prompts_require_local_scope_and_contrast_information_with_documents(self):
        for language in ("bn", "en"):
            prompt = build_system_prompt(language)
            for requirement in ("standalone item", "source_conditions", "A AND B", "X OR Y", "local condition", "Information to enter", "does not require submitting a document", "UNTRUSTED SOURCE MATERIAL", "No outside knowledge"):
                self.assertIn(requirement,prompt)

    def test_quote_first_schema_preserves_scope_without_provider_reference_ids(self):
        schema=service.QuoteFirstAnalysis.model_json_schema()
        self.assertEqual(set(schema["required"]),{"explanation","steps","documents","fees_and_deadlines","unknowns"})
        self.assertFalse(schema["additionalProperties"])
        fields=schema["$defs"]["QuoteClaim"]["properties"]
        self.assertEqual(next(iter(fields)),"source_quotes")
        self.assertNotIn("evidence_ids",fields)
        for rule in ("conditions","exceptions","global eligibility"):
            self.assertIn(rule,fields["source_conditions"]["description"])
        for rule in ("negation","OR"):
            self.assertIn(rule,fields["text"]["description"])

    def analyze_scripted_response(self, source, action, documents, language):
        data = {
            "explanation": [claim(action)],
            "steps": [claim(action)],
            "documents": [claim(text) for text in documents],
            "fees_and_deadlines": {"fees": [], "deadlines": []},
            "unknowns": [],
            "evidence": [{"id": "e1", "excerpt": source}],
        }
        # The mocked response checks transport/post-processing only. It cannot
        # establish that a live model will obey the strengthened instructions.
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-placeholder"}), \
             patch.object(service, "REQUEST_BUDGET"), \
             patch.object(service.genai, "Client") as factory:
            generate = factory.return_value.__enter__.return_value.models.generate_content
            generate.return_value = response(data)
            result = service.analyze_instructions(source, output_language=language)
            generate.assert_called_once()
            request = generate.call_args.kwargs
            self.assertEqual(json.loads(request["contents"]), {"source_text": source})
            self.assertEqual(request["config"].system_instruction, build_system_prompt(language))
            self.assertEqual(request["config"].response_json_schema, service.strip_grammar_bounds(service.QuoteFirstAnalysis.model_json_schema()))
            factory.return_value.__enter__.return_value.models.count_tokens.assert_not_called()
        self.assertEqual(result.steps[0].text, action)
        self.assertEqual([item.text for item in result.documents], documents)
        self.assertTrue(all(item.evidence_status == "quotation_matched" for item in result.explanation + result.steps + result.documents))
        self.assertEqual(result.evidence[0].excerpt, source)
        self.assertTrue(result.evidence[0].excerpt_found)
        self.assertFalse(result.fees_and_deadlines.fees)
        self.assertFalse(result.fees_and_deadlines.deadlines)
        self.assertTrue(any(item.kind == "unverified" and item.category == "fees" for item in result.unknowns))
        return result

    def test_under_18_and_no_nid_requires_one_parent_number_not_a_document(self):
        actions = {
            "bn": "আপনার বয়স ১৮ বছরের কম এবং নিজের জাতীয় পরিচয়পত্র না থাকলে, পিতা অথবা মাতার জাতীয় পরিচয়পত্র নম্বর উল্লেখ করুন।",
            "en": "If you are under ১৮ and have no NID, enter your father's or mother's NID number.",
        }
        for language, action in actions.items():
            with self.subTest(language=language):
                result = self.analyze_scripted_response(PASSPORT_SOURCE, action, [], language)
                self.assertTrue(any(item.kind == "unverified" and item.category == "documents" for item in result.unknowns))

    def test_explicit_document_alternatives_keep_renewal_abroad_condition_and_exception(self):
        actions = {
            "bn": "বিদেশ থেকে পাসপোর্ট নবায়নের আবেদন করলে প্রয়োজনীয় কাগজপত্র জমা দিন, তবে আগে জমা দিয়ে থাকলে আবার দিতে হবে না।",
            "en": "If applying for passport renewal from abroad, submit the required documents, unless already submitted.",
        }
        documents = {
            "bn": "বিদেশ থেকে পাসপোর্ট নবায়নের জন্য মূল জাতীয় পরিচয়পত্র অথবা মূল জন্মনিবন্ধন সনদ (আগে জমা দেওয়া না থাকলে)।",
            "en": "Original NID or original birth registration certificate for passport renewal from abroad (unless already submitted).",
        }
        for language, action in actions.items():
            with self.subTest(language=language):
                result = self.analyze_scripted_response(DOCUMENT_SOURCE, action, [documents[language]], language)
                self.assertEqual(len(result.documents), 1)  # OR stays one alternative requirement.
                self.assertFalse(any(item.kind == "unverified" and item.category == "documents" for item in result.unknowns))


if __name__ == "__main__":
    unittest.main()
