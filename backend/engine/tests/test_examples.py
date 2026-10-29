"""The fictional demo is static, strictly checked, and cannot claim official provenance."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import ai_service
from examples import EXAMPLE_PATH, load_example

class ExampleTests(unittest.TestCase):
    def test_offline_curated_example_has_provenance_and_valid_quotes(self):
        with patch.object(ai_service,"load_settings",side_effect=AssertionError("Saved examples must not load AI settings")),patch.object(ai_service.genai,'Client') as client,patch.object(ai_service,'REQUEST_BUDGET') as budget:
            for language in ('bn','en'):
                for audience in ('general','student'):
                    example,result=load_example(output_language=language,audience=audience)
                    self.assertTrue(example.fictional)
                    self.assertEqual(result.source_type,'curated_example')
                    self.assertIsNone(result.source_url)
                    self.assertTrue(all(item.excerpt_found for item in result.evidence))
                    self.assertTrue(all(item.excerpt in example.source_text for item in result.evidence))
                    self.assertEqual(len(result.fees_and_deadlines.fees),1)
                    self.assertEqual(len(result.fees_and_deadlines.deadlines),1)
                    self.assertIn('কাল্পনিক',example.source_text)
                    if audience=='student': self.assertEqual(result.explanation[0].evidence_ids,['e1','e2','e3'])
        client.assert_not_called(); budget.reserve.assert_not_called()

    def test_missing_or_malformed_example_fails_closed(self):
        with patch.object(Path,'read_text',side_effect=FileNotFoundError): self.assertIsNone(load_example())
        for text in ('{}','not json','null'):
            with patch.object(Path,'read_text',return_value=text): self.assertIsNone(load_example())
        self.assertIsNone(load_example(output_language='unsupported'))
        self.assertIsNone(load_example(audience='unsupported'))

    def test_fabricated_quote_and_official_provenance_are_rejected(self):
        for change in ('quote','fictional','official_url'):
            data=json.loads(EXAMPLE_PATH.read_text(encoding='utf-8'))
            if change=='quote': data['analyses']['bn']['evidence'][0]['excerpt']='উৎসে নেই।'
            elif change=='fictional': data['fictional']=False
            else: data['source_url']='https://example.gov.bd/'
            with patch.object(Path,'read_text',return_value=json.dumps(data)):
                self.assertIsNone(load_example())

if __name__=='__main__': unittest.main()
