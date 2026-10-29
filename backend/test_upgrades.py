from tests.fixtures import wire_payload
import io,json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
import main,ai_service,ocr_service,production_config,openrouter_service
from examples import load_example
from official_examples import load_official_example
from job_progress import report

class UpgradeTests(unittest.TestCase):
 def test_dotenv_preserves_process_values_and_never_evaluates_shell_text(self):
  with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{"GEMINI_MODEL":"host-model"},clear=True):
   path=Path(temp)/".env"
   path.write_text('GEMINI_MODEL=file-model\nGEMINI_API_KEY="fake#key"\nexport FRONTEND_ORIGINS=https://one.test,https://two.test # comment\nTEXT=$(not-a-command)\n',encoding="utf-8")
   production_config.load_local_env(path)
   self.assertEqual(os.environ["GEMINI_MODEL"],"host-model")
   self.assertEqual(os.environ["GEMINI_API_KEY"],"fake#key")
   self.assertEqual(os.environ["FRONTEND_ORIGINS"],"https://one.test,https://two.test")
   self.assertEqual(os.environ["TEXT"],"$(not-a-command)")
 def test_production_does_not_load_a_dotenv_file(self):
  with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{"APP_ENV":"production"},clear=True):
   path=Path(temp)/".env";path.write_text('GEMINI_API_KEY=not-loaded')
   production_config.load_local_env(path)
   self.assertNotIn("GEMINI_API_KEY",os.environ)
 def test_invalid_image_never_loads_credentials_or_dispatches_ocr(self):
  with patch.object(ai_service,"load_settings") as settings,patch.object(ai_service.genai,"Client") as provider:
   with self.assertRaises(ai_service.AnalysisError):ocr_service.extract_image_text(b"invalid","notice.png")
   settings.assert_not_called();provider.assert_not_called()
 def test_official_saved_excerpt_is_bilingual_scoped_and_never_calls_ai(self):
  with patch.object(ai_service.genai,"Client") as provider:
   for language in ("bn","en"):
    source,result=load_official_example(output_language=language)
    self.assertEqual(source.saved_on,"2026-10-21")
    self.assertEqual(result.source_url,source.source_url)
    self.assertTrue(all(e.excerpt_found for e in result.evidence))
    self.assertEqual(len(result.steps),1);self.assertFalse(result.fees_and_deadlines.fees)
    self.assertFalse(result.semantic_review_complete)
   provider.assert_not_called()
 def test_configured_secondary_is_bounded_and_schema_failures_do_not_route(self):
  result=object()
  with patch.dict(os.environ,{"OPENROUTER_API_KEY":"offline-placeholder","GEMINI_FALLBACK_MODEL":"","GROQ_API_KEY":""},clear=True),patch.object(ai_service,"_analyze_gemini",side_effect=ai_service.AnalysisError("rate_limit_or_quota","fixed")),patch.object(ai_service,"_analyze_openrouter",return_value=result) as secondary:
   self.assertIs(ai_service.analyze_instructions("Public notice"),result);secondary.assert_called_once()
  with patch.object(ai_service,"_analyze_gemini",side_effect=ai_service.AnalysisError("malformed_response","fixed")),patch.object(ai_service,"_analyze_openrouter") as secondary:
   with self.assertRaises(ai_service.AnalysisError):ai_service.analyze_instructions("Public notice")
   secondary.assert_not_called()
 def test_gemini_secondary_model_is_used_once_without_mutating_process_configuration(self):
  with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder","GEMINI_MODEL":"primary","GEMINI_FALLBACK_MODEL":"secondary"},clear=True),patch.object(ai_service,"_analyze_gemini",side_effect=[ai_service.AnalysisError("service_busy","fixed"),"result"]) as generation:
   self.assertEqual(ai_service.analyze_instructions("Public notice"),"result")
   self.assertEqual(generation.call_count,2)
   self.assertEqual(generation.call_args.kwargs["settings_override"].model,"secondary")
   self.assertEqual(os.environ["GEMINI_MODEL"],"primary")
 def test_degraded_review_is_explicit_and_never_marks_ai_review_complete(self):
  source,checked=load_example()
  for code in ("timeout","rate_limit_or_quota"):
   degraded=ai_service.deterministic_review_fallback(checked,ai_service.AnalysisError(code,"fixed"),source_text=source.source_text)
   public=main.public_result(degraded)
   self.assertEqual(public["review_mode"],"deterministic_only")
   self.assertFalse(public["semantic_review_complete"]);self.assertTrue(public["has_guidance"])
  self.assertEqual(ai_service.deterministic_review_fallback(checked,ai_service.AnalysisError("malformed_response","fixed"),source_text=source.source_text).review_mode,"deterministic_only")
  with self.assertRaises(ai_service.AnalysisError):main.public_result(checked)
 def test_paid_or_qwen_openrouter_configuration_is_rejected_before_transport(self):
  for model in ("qwen/model:free","openai/paid-model"):
   with patch.object(openrouter_service.httpx,"Client") as transport:
    with self.assertRaises(openrouter_service.OpenRouterError):openrouter_service.generate_json(api_key=ai_service.SecretStr("offline"),model=model,system_prompt="JSON",message="public",schema={})
    transport.assert_not_called()
 def test_openrouter_transport_sends_zero_price_ceiling_and_validates_the_model(self):
  import httpx
  captured=[];real_client=httpx.Client
  def respond(request):
   captured.append(json.loads(request.content))
   self.assertEqual(request.url.host,"openrouter.ai")
   return httpx.Response(200,json={"model":openrouter_service.OPENROUTER_MODEL,"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"{}"}}]})
  def client(**options):return real_client(**options,transport=httpx.MockTransport(respond))
  with patch.object(openrouter_service.httpx,"Client",side_effect=client):
   self.assertEqual(openrouter_service.generate_json(api_key=ai_service.SecretStr("offline-placeholder"),system_prompt="JSON",message="public",schema={}),"{}")
  self.assertEqual(captured[0]["provider"]["max_price"],{"prompt":0,"completion":0,"request":0})
  self.assertFalse(captured[0]["stream"])
 def test_real_sdk_review_quota_failure_returns_explicitly_degraded_result_without_retry(self):
  import httpx
  from google.genai import types
  from request_control import RequestBudget
  from tests.fixtures import SOURCE,payload
  requests=[];clock=[0.0];real_client=ai_service.genai.Client
  def respond(request):
   requests.append(json.loads(request.content))
   if len(requests)==2:return httpx.Response(429,json={"error":{"code":429,"message":"offline quota"}})
   return httpx.Response(200,json={"candidates":[{"content":{"role":"model","parts":[{"text":json.dumps(wire_payload(payload()))}]},"finishReason":"STOP"}]})
  def client(**options):return real_client(vertexai=False,api_key="offline-placeholder",http_options=types.HttpOptions(api_version=ai_service.API_VERSION,retry_options=types.HttpRetryOptions(attempts=1),client_args={"transport":httpx.MockTransport(respond)}))
  with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-placeholder","DETERMINISTIC_REVIEW_FALLBACK":"1"},clear=True),patch.object(ai_service.genai,"Client",side_effect=client),patch.object(ai_service,"REQUEST_BUDGET",RequestBudget(clock=lambda:clock[0])),patch.object(ai_service,"sleep",side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)):
   result=ai_service.analyze_instructions(SOURCE)
  self.assertEqual(len(requests),2)
  self.assertFalse(result.semantic_review_complete)
  self.assertEqual(main.public_result(result)["review_mode"],"deterministic_only")
 def test_sse_is_owned_and_streams_real_review_stage_without_starting_new_work(self):
  _,result=load_example();result=result.model_copy(update={"semantic_review_complete":True})
  def work(*args,**kwargs):
   time.sleep(.4);report("verifying");time.sleep(.4);return result
  with TestClient(main.app) as client,patch.object(ai_service,"analyze_instructions",side_effect=work) as provider:
   headers={"X-Session-Token":client.post("/api/session").json()["token"]}
   job=client.post("/api/analysis",headers=headers,json={"text":"Public instructions","reviewed":True,"kind":"text","revision":"stream"}).json()["job_id"]
   self.assertEqual(client.get(f"/api/jobs/{job}/stream").status_code,401)
   response=client.get(f"/api/jobs/{job}/stream",headers=headers)
   self.assertIn("text/event-stream",response.headers["content-type"])
   events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
   self.assertIn("verifying",[event["stage"] for event in events])
   self.assertEqual(events[-1]["stage"],"completed")
   self.assertEqual(events[-1]["status"],"succeeded");provider.assert_called_once()
