"""v2 application boundaries; browser/editor contracts are in React interaction tests."""
import json,time,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main,ai_service
from examples import load_example
from guides import load_guides
from tests.fixtures import SOURCE,payload,misplaced_missing_notices

class AppTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(main.app);self.client.__enter__()
        self.addCleanup(self.client.__exit__,None,None,None)
        self.headers={"X-Session-Token":self.client.post('/api/session').json()['token']}
        self.body=dict(text=SOURCE,kind='text',reviewed=True,revision='source')
    def submit(self,**changes):
        return self.client.post('/api/analysis',headers=self.headers,json={**self.body,**changes})
    def wait(self,response):
        self.assertEqual(response.status_code,202)
        for _ in range(200):
            value=self.client.get('/api/jobs/'+response.json()['job_id'],headers=self.headers).json()
            if value['status'] in ('succeeded','failed'):return value
            time.sleep(.005)
        self.fail('Job did not finish')
    def checked(self,data=None,reviewed=True):
        value=ai_service.check_evidence(ai_service.ProviderAnalysis.model_validate(payload() if data is None else data),SOURCE,source_type='user_provided',source_url=None,model=ai_service.DEFAULT_MODEL)
        if reviewed:
            from tests.test_semantic_review import scripted_review
            value=ai_service.apply_semantic_review(value,SOURCE,scripted_review(value,SOURCE,set(ai_service.review_candidates(value))))
        return value
    def test_initial_health_and_examples_never_start_analysis(self):
        with patch.object(ai_service,'analyze_instructions') as provider:
            self.assertEqual(self.client.get('/api/health').status_code,200)
            self.assertTrue(self.client.get('/api/example').json()['fictional'])
            provider.assert_not_called()
    def test_invalid_input_never_calls_provider(self):
        with patch.object(ai_service,'analyze_instructions') as provider:
            for text in ('',' \n\t','x'*50001):self.assertEqual(self.submit(text=text).status_code,422)
            provider.assert_not_called()
    def test_unreviewed_generated_result_is_never_published(self):
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked(reviewed=False)):
            value=self.wait(self.submit())
            self.assertEqual(value['error'],'review_failed');self.assertIsNone(value['result'])
    def test_reviewed_result_read_is_stable_without_new_generation(self):
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked()) as provider:
            response=self.submit();first=self.wait(response)
            self.assertEqual(first['status'],'succeeded')
            self.assertEqual(self.wait(response),first);provider.assert_called_once()
    def test_changed_source_with_same_request_id_is_rejected(self):
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked()) as provider:
            self.wait(self.submit(request_id='stable'))
            self.assertEqual(self.submit(request_id='stable',text=SOURCE+' changed').status_code,409)
            provider.assert_called_once()
    def test_missing_notices_do_not_become_fee_or_deadline_facts(self):
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked(misplaced_missing_notices())):
            value=self.wait(self.submit())['result']
            self.assertFalse(value['sections']['fees']);self.assertFalse(value['sections']['deadlines'])
            self.assertTrue(value['unknowns'])
    def test_failed_resubmission_contains_no_previous_result(self):
        with patch.object(ai_service,'analyze_instructions',side_effect=[self.checked(),ai_service.AnalysisError('rate_limit_or_quota','PRIVATE')]):
            self.assertEqual(self.wait(self.submit())['status'],'succeeded')
            failed=self.wait(self.submit(text=SOURCE+' changed',revision='changed'))
            self.assertIsNone(failed['result']);self.assertNotIn('PRIVATE',str(failed))
    def test_missing_key_has_fixed_error_and_no_provider_dispatch(self):
        with patch.dict(ai_service.os.environ,{},clear=True),patch.object(ai_service.genai,'Client') as provider:
            value=self.wait(self.submit())
            self.assertEqual(value['error'],'missing_key');self.assertIsNone(value['result'])
            provider.assert_not_called()
    def test_safe_diagnostics_are_not_raw_public_provider_messages(self):
        from google.genai import errors
        diagnostic=ai_service.provider_diagnostics(errors.APIError(400,{'error':{'message':'PRIVATE'}}),model=ai_service.DEFAULT_MODEL)
        with patch.object(ai_service,'analyze_instructions',side_effect=ai_service.AnalysisError('provider_error','PRIVATE',diagnostics=diagnostic)):
            value=self.wait(self.submit());self.assertEqual(value['error'],'provider_error')
            self.assertNotIn('PRIVATE',str(value));self.assertIsNone(value['result'])
    def test_unexpected_boundary_exception_is_sanitized(self):
        with patch.object(ai_service,'analyze_instructions',side_effect=RuntimeError('PRIVATE')):
            value=self.wait(self.submit());self.assertEqual(value['error'],'unexpected')
            self.assertNotIn('PRIVATE',str(value));self.assertIsNone(value['result'])
    def test_fabricated_document_remains_withheld_despite_review_approval(self):
        data=payload();data['documents'][0]['text']='Fabricated document';data['evidence'][1]['excerpt']='Fabricated quotation'
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked(data)):
            value=self.wait(self.submit())['result']
            self.assertNotIn('Fabricated document',str(value['sections']));self.assertTrue(value['partial'])
    def test_identical_request_reuses_completed_result(self):
        with patch.object(ai_service,'analyze_instructions',return_value=self.checked()) as provider:
            first=self.submit(request_id='replay');self.wait(first)
            self.assertEqual(self.submit(request_id='replay').json(),first.json());provider.assert_called_once()
    def test_provider_executes_with_session_locked_and_failure_unlocks(self):
        token=self.headers['X-Session-Token']
        def work(*args,**kwargs):
            self.assertTrue(main.sessions[token]['active'])
            raise ai_service.AnalysisError('timeout','PRIVATE')
        with patch.object(ai_service,'analyze_instructions',side_effect=work):
            self.assertEqual(self.wait(self.submit())['error'],'timeout')
            self.assertIsNone(main.sessions[token]['active'])
    def test_saved_example_survives_quota_failure_without_provider_retry(self):
        with patch.object(ai_service,'analyze_instructions',side_effect=ai_service.AnalysisError('rate_limit_or_quota','PRIVATE')) as provider:
            self.assertEqual(self.wait(self.submit())['error'],'rate_limit_or_quota')
            example=self.client.get('/api/example').json();self.assertTrue(example['fictional'])
            provider.assert_called_once()

class PreservedBehaviorTests(unittest.TestCase):
    def test_character_limit_counts_original_whitespace(self):
        self.assertEqual(main.AnalysisBody(text='ক'*10000,kind='text',reviewed=True,revision='limit').text,'ক'*10000)
        self.assertEqual(len(main.AnalysisBody(text='ক'*50000,kind='text',reviewed=True,revision='limit').text),50000)
        with self.assertRaises(ValueError):main.AnalysisBody(text=' '*50001,kind='text',reviewed=True,revision='limit')

    def test_guide_metadata_cannot_promote_itself_to_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'guides.json'
            path.write_text(json.dumps([{'verification_status':'verified','instruction_text':'private','last_verified':'2026-10-21'}]),encoding='utf-8')
            self.assertEqual(load_guides(path),[])

    def test_malformed_and_missing_guides_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'guides.json'
            self.assertEqual(load_guides(path),[])
            for raw in ('not json','{}','[null, 5]'):
                path.write_text(raw,encoding='utf-8'); self.assertEqual(load_guides(path),[])
