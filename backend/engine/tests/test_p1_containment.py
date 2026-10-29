"""Historical scope failures remain failures; v2 public filtering fails closed."""
import copy,hashlib,json,time,threading,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main,ai_service as service
from examples import load_example
DATA=Path(__file__).parent/'data'
EPASSPORT=json.loads((DATA/'epassport_scope.json').read_text(encoding='utf-8'))
P1=json.loads((DATA/'p1_scope.json').read_text(encoding='utf-8'))
def checked(case, data=None):
    return service.check_evidence(
        service.ProviderAnalysis.model_validate(data or case['provider_output']),
        case['source'], source_type='user_provided', source_url=None,
        model=case['recorded_model'],
    )


class P1ContainmentTests(unittest.TestCase):
    def assert_rejected(self,result):
        with self.assertRaises(service.AnalysisError) as caught:main.public_result(result)
        self.assertEqual(caught.exception.code,'review_failed')
    def test_exact_recorded_failure_remains_a_failure(self):
        self.assertEqual(hashlib.sha256(EPASSPORT['source'].encode()).hexdigest(), EPASSPORT['source_sha256'])
        result = checked(EPASSPORT)
        for item in (result.steps[12], result.documents[5]):
            self.assertEqual(item.evidence_ids, ['e20'])
            self.assertEqual(item.evidence_status, 'quotation_matched')
            self.assertIn('জাতীয় পরিচয়পত্র (NID), অনলাইন জন্মনিবন্ধন', item.text)
            self.assertNotIn('১৮', item.text)
            self.assertNotIn('মিশন', item.text)
        self.assertIn('১৮-২০', EPASSPORT['source'])
        self.assertIn('বিদেশস্থ বাংলাদেশ মিশন', EPASSPORT['source'])
        self.assertEqual(result.fees_and_deadlines.fees, [])
        self.assertEqual(result.fees_and_deadlines.deadlines, [])
        self.assertIn('ভ্যাট', result.explanation[5].text)
        for item, value in zip(result.explanation[6:9], ('২', '৭', '১৫')):
            self.assertIn(value+' কর্মদিবস', item.text)
            self.assertIn('অন্যান্য সকল তথ্য সঠিক থাকা সাপেক্ষে', item.text)
        self.assertFalse(any(item.kind == 'contradiction' for item in result.unknowns))
        self.assertEqual({e.id for e in result.evidence if not e.excerpt_found}, {'e22', 'e23'})
        self.assertTrue(all(c.evidence_status == 'unsupported' for c in result.steps + result.documents
                            if {'e22','e23'}.intersection(c.evidence_ids)))

    def test_saved_failures_are_rejected_without_rewriting_the_original(self):
        for case in (EPASSPORT,P1):
            result=checked(case);before=result.model_dump()
            self.assertTrue(result.steps and result.documents)
            self.assert_rejected(result);self.assertEqual(result.model_dump(),before)
    def test_repaired_category_routing_cannot_bypass_review_gate(self):
        data=copy.deepcopy(EPASSPORT['provider_output'])
        data['fees_and_deadlines']['fees']=[data['explanation'][5]]
        data['fees_and_deadlines']['deadlines']=data['explanation'][6:9]
        result=checked(EPASSPORT,data)
        self.assertTrue(result.fees_and_deadlines.fees and result.fees_and_deadlines.deadlines)
        self.assert_rejected(result)
    def test_gate_does_not_depend_on_fixture_ids_or_provenance_label(self):
        data=copy.deepcopy(P1['provider_output'])
        renumber={e['id']:'e'+str(i+91) for i,e in enumerate(data['evidence'])}
        for e in data['evidence']:e['id']=renumber[e['id']]
        for items in (data['explanation'],data['steps'],data['documents'],data['fees_and_deadlines']['fees'],data['unknowns']):
            for item in items:item['evidence_ids']=[renumber[ref] for ref in item['evidence_ids']]
        result=checked(P1,data)
        for kind in ('user_provided','verified_guide','curated_example'):
            self.assert_rejected(result.model_copy(update={'source_type':kind}))
    def test_failed_api_result_remains_withheld_on_repeated_reads(self):
        from tests.test_error_recovery import ManualRecoveryTests
        harness=ManualRecoveryTests();harness.setUp()
        try:
            with patch.object(service,'analyze_instructions',return_value=checked(EPASSPORT)) as provider:
                response=harness.submit();first=harness.wait(response)
                self.assertEqual(first['error'],'review_failed');self.assertIsNone(first['result'])
                self.assertEqual(harness.wait(response),first);provider.assert_called_once()
        finally:harness.doCleanups()
    def test_saved_examples_require_explicit_demo_export_and_are_not_ai_reviewed(self):
        for language in ('bn','en'):
            for audience in ('general','student'):
                _,result=load_example(output_language=language,audience=audience)
                self.assert_rejected(result)
                exported=main.public_result(result,demo=True)
                self.assertTrue(exported['demo']);self.assertTrue(exported['has_guidance'])
                self.assertFalse(exported['semantic_review_complete'])

class AnalysisPauseTests(unittest.TestCase):
    def test_service_stops_before_configuration_budget_and_provider(self):
        with patch.object(service,'ANALYSIS_ENABLED',False),patch.object(service,'load_settings') as settings,patch.object(service.REQUEST_BUDGET,'reserve') as reserve,patch.object(service.genai,'Client') as provider:
            with self.assertRaises(service.AnalysisError) as caught:service.analyze_instructions(P1['source'])
            self.assertEqual(caught.exception.code,'analysis_paused')
            settings.assert_not_called();reserve.assert_not_called();provider.assert_not_called()
    def test_paused_api_cannot_queue_analysis_but_examples_stay_available(self):
        with TestClient(main.app) as client,patch.object(service,'ANALYSIS_ENABLED',False),patch.object(service,'analyze_instructions') as provider:
            headers={'X-Session-Token':client.post('/api/session').json()['token']}
            for language in ('bn','en'):
                response=client.post('/api/analysis',headers=headers,json={'text':P1['source'],'language':language,'kind':'text','reviewed':True,'revision':'paused'})
                self.assertEqual(response.status_code,503);self.assertEqual(response.json()['detail'],'analysis_paused')
                self.assertTrue(client.get('/api/example',params={'language':language}).json()['fictional'])
            self.assertFalse(main.jobs);provider.assert_not_called()
    def test_queued_analysis_observes_emergency_pause_before_credentials(self):
        from tests.test_gemini_ocr import image_bytes
        entered=threading.Event();release=threading.Event()
        def extract(*args):entered.set();release.wait(2);return 'Public source'
        with TestClient(main.app) as client,patch.object(main,'extract_image_text',side_effect=extract),patch.object(service,'load_settings') as settings:
            first={'X-Session-Token':client.post('/api/session').json()['token']}
            second={'X-Session-Token':client.post('/api/session').json()['token']}
            try:
                client.post('/api/extract/image?revision=blocking',headers={**first,'Content-Type':'image/png'},content=image_bytes())
                self.assertTrue(entered.wait(1))
                response=client.post('/api/analysis',headers=second,json={'text':P1['source'],'kind':'text','reviewed':True,'revision':'queued'})
                self.assertEqual(response.status_code,202)
                with patch.object(service,'ANALYSIS_ENABLED',False):
                    release.set()
                    for _ in range(200):
                        snapshot=client.get('/api/jobs/'+response.json()['job_id'],headers=second).json()
                        if snapshot['status']=='failed':break
                        time.sleep(.005)
                    self.assertEqual(snapshot['error'],'analysis_paused');self.assertIsNone(snapshot['result'])
                settings.assert_not_called();self.assertIsNone(main.sessions[second['X-Session-Token']]['active'])
            finally:release.set()

class P1RootCauseTests(unittest.TestCase):
    def test_global_scope_is_in_explanation_but_missing_from_all_seven_standalone_requirements(self):
        result=checked(P1)
        self.assertIn('জেলার বাসিন্দা',result.explanation[0].text)
        self.assertIn('বর্তমানে শিক্ষার্থী',result.explanation[0].text)
        requirements=result.steps+result.documents+result.fees_and_deadlines.fees
        self.assertEqual(len(requirements),7)
        for item in requirements:
            self.assertEqual(item.evidence_status,'quotation_matched')
            self.assertNotIn('e1',item.evidence_ids)
            self.assertNotIn('জেলার বাসিন্দা',item.text)
            self.assertNotIn('বর্তমানে শিক্ষার্থী',item.text)
        fee=result.fees_and_deadlines.fees[0]
        self.assertEqual(fee.evidence_ids,['e4'])
        excerpt=next(e.excerpt for e in result.evidence if e.id=='e4')
        self.assertIn('প্রতিবন্ধী',excerpt)
        self.assertNotIn('প্রতিবন্ধী',fee.text)
        self.assertIn('সাধারণ',fee.text)  # An undefined group does not state the exception.

    def test_identical_local_quote_cannot_prove_global_applicability(self):
        # The same action/quote is unconditional alone and overbroad under the
        # global eligibility sentence. The current checker returns the same
        # quotation status in both cases: a diagnostic, never semantic acceptance.
        action=copy.deepcopy(P1['provider_output']['steps'][0])
        evidence=copy.deepcopy(P1['provider_output']['evidence'][1])
        data={'explanation':[action],'steps':[action],'documents':[],
              'fees_and_deadlines':{'fees':[],'deadlines':[]},'unknowns':[],'evidence':[evidence]}
        for source in (P1['source'],evidence['excerpt']):
            result=service.check_evidence(service.ProviderAnalysis.model_validate(data),source,
                source_type='user_provided',source_url=None,model=P1['recorded_model'])
            self.assertEqual(result.steps[0].evidence_status,'quotation_matched')
            self.assertEqual(result.steps[0].text,action['text'])
