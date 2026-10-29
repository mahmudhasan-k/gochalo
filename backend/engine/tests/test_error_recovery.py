"""Explicit v2 recovery and admission checks; mocked transports only."""
import os,time,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from google.genai import errors
import main,ai_service as service
from examples import load_example
from request_control import RequestBudget
from tests.fixtures import SOURCE,response

class ManualRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(main.app);self.client.__enter__()
        self.addCleanup(self.client.__exit__,None,None,None)
        self.headers={"X-Session-Token":self.client.post('/api/session').json()['token']}
    def submit(self,language='bn',text=SOURCE,request_id=''):
        return self.client.post('/api/analysis',headers=self.headers,json={"text":text,"language":language,"reviewed":True,"kind":"text","revision":"recovery","request_id":request_id})
    def wait(self,response):
        self.assertEqual(response.status_code,202)
        for _ in range(200):
            value=self.client.get('/api/jobs/'+response.json()['job_id'],headers=self.headers).json()
            if value['status'] in ('succeeded','failed'):return value
            time.sleep(.005)
        self.fail('Recovery job did not finish')
    def reviewed(self):
        _,value=load_example();return value.model_copy(update={"semantic_review_complete":True})
    def test_retryable_failures_need_explicit_new_request_and_preserve_language(self):
        for language in ('bn','en'):
            for code in ('service_busy','rate_limit_or_quota','timeout','network_error'):
                with self.subTest(language=language,code=code),patch.object(service,'analyze_instructions',side_effect=[service.AnalysisError(code,'PRIVATE'),self.reviewed()]) as provider:
                    first=self.submit(language);failed=self.wait(first)
                    self.assertEqual(failed['error'],code);self.assertIsNone(failed['result'])
                    self.assertNotIn('PRIVATE',str(failed))
                    self.wait(first);self.client.get('/api/health');self.assertEqual(provider.call_count,1)
                    self.assertEqual(self.wait(self.submit(language))['status'],'succeeded')
                    provider.assert_called_with(SOURCE,output_language=language)
                    self.assertEqual(provider.call_count,2)
    def test_explicit_retry_uses_current_source_and_language(self):
        with patch.object(service,'analyze_instructions',side_effect=[service.AnalysisError('service_busy','PRIVATE'),self.reviewed()]) as provider:
            self.wait(self.submit())
            self.assertEqual(self.wait(self.submit('en',SOURCE+' changed'))['status'],'succeeded')
            provider.assert_called_with(SOURCE+' changed',output_language='en')
    def test_rate_guard_spaces_explicit_retry_without_hidden_transport_retry(self):
        clock=[0.0]
        with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder"}),patch.object(service,'REQUEST_BUDGET',RequestBudget(clock=lambda:clock[0])),patch.object(service,'sleep',side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)) as wait,patch.object(service,'review_semantics',side_effect=lambda result,*args,**kwargs:result),patch.object(service.genai,'Client') as factory:
            generate=factory.return_value.__enter__.return_value.models.generate_content
            generate.side_effect=[errors.APIError(503,{"error":{"message":"PRIVATE"}}),response()]
            with self.assertRaises(service.AnalysisError):service.analyze_instructions(SOURCE)
            self.assertEqual(generate.call_count,1)
            service.analyze_instructions(SOURCE)
            self.assertEqual(generate.call_count,2);wait.assert_called_once_with(2)
            self.assertEqual(clock[0],2)
    def test_configuration_errors_do_not_auto_retry_or_publish_results(self):
        for code in ('missing_key','configuration','access_denied'):
            with self.subTest(code=code),patch.object(service,'analyze_instructions',side_effect=service.AnalysisError(code,'PRIVATE')) as provider:
                response=self.submit();value=self.wait(response)
                self.assertEqual(value['error'],code);self.assertIsNone(value['result'])
                self.wait(response);provider.assert_called_once()
    def test_stale_request_id_reuses_valid_result_without_new_generation(self):
        with patch.object(service,'analyze_instructions',return_value=self.reviewed()) as provider:
            first=self.submit(request_id='completed');before=self.wait(first)
            replay=self.submit(request_id='completed')
            self.assertEqual(replay.json(),first.json());self.assertEqual(self.wait(replay),before)
            provider.assert_called_once()
    def test_failed_provider_attempts_remain_possible_after_cooldown_and_example_is_offline(self):
        clock=[0.0]
        with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder"}),patch.object(service,'REQUEST_BUDGET',RequestBudget(clock=lambda:clock[0])),patch.object(service.genai,'Client') as factory:
            generate=factory.return_value.__enter__.return_value.models.generate_content
            generate.side_effect=errors.APIError(503,{"error":{"message":"PRIVATE"}})
            for now in (0,13,26,39,52):
                clock[0]=now
                with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(SOURCE)
                self.assertEqual(caught.exception.code,'service_busy')
            self.assertEqual(generate.call_count,5)
            for language in ('bn','en'):
                self.assertTrue(self.client.get('/api/example',params={"language":language}).json()['fictional'])
            self.assertEqual(generate.call_count,5)
