"""Keep P1 visibly unresolved; historical replay is not current-model acceptance."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import ai_service as service

CASE=json.loads((Path(__file__).parent/'data/p1_scope.json').read_text(encoding='utf-8'))

def replay():
    return service.check_evidence(service.ProviderAnalysis.model_validate(CASE['provider_output']),CASE['source'],
        source_type='user_provided',source_url=None,model=CASE['recorded_model'])

class P1ScopeTests(unittest.TestCase):
    def test_historical_schema_and_quote_pass_is_not_semantic_acceptance(self):
        with patch.object(service.genai,'Client') as provider:
            result=replay()
        self.assertEqual(result.model,CASE['recorded_model'])
        self.assertTrue(all(item.excerpt_found for item in result.evidence))
        self.assertTrue(all(item.evidence_status=='quotation_matched' for item in result.steps+result.documents+result.fees_and_deadlines.fees))
        self.assertEqual(len(CASE['expected']),9)
        provider.assert_not_called()

    @unittest.expectedFailure
    def test_archived_requirements_preserve_global_eligibility_scope(self):
        # This fixture-specific oracle is a release criterion, never a production
        # detector or automatic repair. Remove expectedFailure only after a real fix.
        result=replay()
        scope_ids={item.id for item in result.evidence if 'এই জেলার বাসিন্দা' in item.excerpt and 'বর্তমানে শিক্ষার্থী' in item.excerpt}
        self.assertTrue(scope_ids)
        for item in result.steps+result.documents+result.fees_and_deadlines.fees:
            self.assertTrue(scope_ids.intersection(item.evidence_ids),item.text)
            self.assertIn('এই জেলার বাসিন্দা',item.text)
            self.assertIn('বর্তমানে শিক্ষার্থী',item.text)

if __name__=='__main__': unittest.main()
