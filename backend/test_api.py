from tests.fixtures import wire_payload
import sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import main,ai_service
from examples import load_example
from fastapi.testclient import TestClient

class ApiTests(unittest.TestCase):
 def setUp(self):
  self.ctx=TestClient(main.app); self.c=self.ctx.__enter__()
  self.h={"X-Session-Token":self.c.post("/api/session").json()["token"]}
 def tearDown(self): self.ctx.__exit__(None,None,None)
 def body(self): return dict(text="Public instructions",language="bn",kind="text",reviewed=True,revision="r1")
 def wait(self,job):
  for _ in range(100):
   data=self.c.get("/api/jobs/"+job,headers=self.h).json()
   if data["status"] in ("failed","succeeded"): return data
   time.sleep(.01)
  self.fail("job timeout")
 def test_health_and_demo_without_provider(self):
  with patch.object(ai_service,"analyze_instructions",side_effect=AssertionError("network")):
   self.assertEqual(self.c.get("/api/health").status_code,200)
   for lang in ("bn","en"):
    r=self.c.get("/api/example?language="+lang)
    self.assertEqual(r.status_code,200); self.assertTrue(r.json()["result"]["demo"])
 def test_session_required(self):
  self.assertEqual(self.c.post("/api/analysis",json=self.body()).status_code,401)
 def test_request_lookup_and_replay_are_owned_bounded_and_do_not_repeat_provider_work(self):
  import threading
  release=threading.Event()
  def work(*args,**kwargs):
   release.wait(2)
   raise ai_service.AnalysisError("review_failed","private detail")
  body={**self.body(),"request_id":"lost-response"}
  with patch.object(ai_service,"analyze_instructions",side_effect=work) as provider,patch.object(main,"MAX_RETAINED_JOBS",1):
   try:
    first=self.c.post("/api/analysis",json=body,headers=self.h).json()["job_id"]
    self.assertEqual(self.c.get("/api/requests/lost-response",headers=self.h).json(),{"job_id":first})
    self.assertEqual(self.c.post("/api/analysis",json=body,headers=self.h).json(),{"job_id":first})
    other={"X-Session-Token":self.c.post("/api/session").json()["token"]}
    self.assertEqual(self.c.get("/api/requests/lost-response",headers=other).status_code,404)
    self.assertEqual(self.c.get("/api/requests/lost-response").status_code,401)
   finally:release.set()
   self.assertEqual(self.wait(first)["status"],"failed")
   self.assertEqual(self.c.post("/api/analysis",json=body,headers=self.h).json(),{"job_id":first})
   conflict=self.c.post("/api/analysis",json={**body,"text":"Different source"},headers=self.h)
   self.assertEqual(conflict.status_code,409)
   self.assertEqual(conflict.json(),{"detail":"request_id_conflict"})
   provider.assert_called_once()
   main.jobs[first]["created"]=time.monotonic()-main.TTL-1
   self.assertEqual(self.c.get("/api/requests/lost-response",headers=self.h).status_code,404)
   self.assertEqual(self.c.get("/api/requests/"+"x"*81,headers=self.h).status_code,422)
 def test_automatic_source_input_keeps_internal_review_required(self):
  body=self.body();body["reviewed"]=False
  with patch.object(ai_service,"analyze_instructions",side_effect=ai_service.AnalysisError("review_failed","private")) as call:
   response=self.c.post("/api/analysis",json=body,headers=self.h)
   self.assertEqual(response.status_code,202)
   result=self.wait(response.json()["job_id"])
   self.assertEqual(result["status"],"failed");self.assertIsNone(result["result"])
   call.assert_called_once()
 def test_invalid_input_is_not_echoed(self):
  body=self.body();body["text"]="PRIVATE_SOURCE"*5000
  r=self.c.post("/api/analysis",json=body,headers=self.h)
  self.assertEqual(r.status_code,422);self.assertNotIn("PRIVATE_SOURCE",r.text)
 def test_private_link_rejected(self):
  with patch.object(main.url_input,"extract_url") as call:
   r=self.c.post("/api/extract/link",json=dict(url="http://127.0.0.1",revision="r1"),headers=self.h)
   self.assertEqual(r.status_code,400);call.assert_not_called()
 def test_review_failure_and_job_ownership(self):
  with patch.object(ai_service,"analyze_instructions",side_effect=ai_service.AnalysisError("service_busy","secret detail")):
   job=self.c.post("/api/analysis",json=self.body(),headers=self.h).json()["job_id"]
   data=self.wait(job)
  self.assertEqual(data["status"],"failed");self.assertIsNone(data["result"])
  self.assertNotIn("secret detail",str(data));self.assertEqual(data["revision"],"r1")
  other=self.c.post("/api/session").json()["token"]
  self.assertEqual(self.c.get("/api/jobs/"+job,headers={"X-Session-Token":other}).status_code,404)
 def test_owned_diagnostics_expose_only_allowlisted_provider_summary(self):
  safe=ai_service.ProviderDiagnostics(http_status=400,error_code=400,error_status="INVALID_ARGUMENT",
   message="The provider rejected request arguments; unrecognized details omitted for privacy.",
   model="gemini-3.5-flash-lite",sdk_version="test",api_version="v1beta",
   operation="generateContent",schema_mode="response_json_schema",timeout_ms=60000,maximum_attempts=1)
  with patch.object(ai_service,"analyze_instructions",side_effect=ai_service.AnalysisError(
      "provider_error","safe user message",diagnostics=safe)):
   job=self.c.post("/api/analysis",json=self.body(),headers=self.h).json()["job_id"]
   self.wait(job)
  diagnostics=self.c.get("/api/jobs/"+job+"/diagnostics",headers=self.h)
  self.assertEqual(diagnostics.status_code,200)
  self.assertEqual(diagnostics.json()["provider_diagnostics"],safe.model_dump())
  self.assertNotIn("GEMINI_API_KEY",diagnostics.text)
  self.assertNotIn("headers",diagnostics.text)
 def test_unreviewed_results_fail_closed(self):
  _,result=load_example()
  with self.assertRaises(ai_service.AnalysisError): main.public_result(result)
 def test_withheld_wording_never_serialized(self):
  _,result=load_example()
  unsafe=result.steps[0].model_copy(update=dict(text="UNSAFE_CLAIM",semantic_status="withheld"))
  result=result.model_copy(update=dict(steps=[unsafe],semantic_review_complete=True))
  output=main.public_result(result)
  self.assertNotIn("UNSAFE_CLAIM",str(output));self.assertEqual(output["sections"]["steps"],[])
  self.assertTrue(output["partial"])

 def test_successful_link_preserves_provenance_and_revision(self):
  from types import SimpleNamespace
  from datetime import datetime,timezone
  from unittest.mock import AsyncMock
  value=SimpleNamespace(text="Original public notice",requested_url="https://example.gov.bd/a",returned_url="https://example.gov.bd/b",retrieved_at=datetime.now(timezone.utc),title="Notice")
  with patch.object(main.url_input,"extract_url",new=AsyncMock(return_value=value)) as extract:
   body=dict(url=value.requested_url,revision="link-r2",request_id="link-request")
   r=self.c.post("/api/extract/link",json=body,headers=self.h)
   data=self.wait(r.json()["job_id"])
   self.assertEqual(self.c.post("/api/extract/link",json=body,headers=self.h).json(),r.json())
   extract.assert_awaited_once()
  self.assertEqual(data["status"],"succeeded")
  self.assertEqual(data["revision"],"link-r2")
  self.assertEqual(data["result"]["requested_url"],value.requested_url)
  self.assertEqual(data["result"]["returned_url"],value.returned_url)
  self.assertEqual(data["result"]["retrieved_at"],value.retrieved_at.isoformat())
 def test_image_success_uses_separate_extraction_without_analysis(self):
  import io
  from PIL import Image
  image=io.BytesIO();Image.new("RGB",(10,10),"white").save(image,format="PNG")
  with patch.object(main,"extract_image_text",return_value="Public notice text") as extract,patch.object(ai_service,"analyze_instructions") as analyze:
   response=self.c.post("/api/extract/image?revision=image-r1&request_id=image-request",content=image.getvalue(),headers={**self.h,"Content-Type":"image/png"})
   data=self.wait(response.json()["job_id"])
   self.assertEqual(data["result"]["text"],"Public notice text")
   repeated=self.c.post("/api/extract/image?revision=image-r1&request_id=image-request",content=image.getvalue(),headers={**self.h,"Content-Type":"image/png"})
   self.assertEqual(repeated.json(),response.json())
   extract.assert_called_once();analyze.assert_not_called()
 def test_upload_mime_and_size_rejected_before_provider(self):
  with patch.object(main,"extract_image_text") as extract:
   r=self.c.post("/api/extract/image?revision=r1",content=b"not image",headers={**self.h,"Content-Type":"text/plain"})
   self.assertEqual(r.status_code,400)
   r=self.c.post("/api/extract/image?revision=r1",content=b"x"*(5*1024*1024+1),headers={**self.h,"Content-Type":"image/png"})
   self.assertEqual(r.status_code,413);extract.assert_not_called()
 def test_expired_session_rejected(self):
  main.sessions[self.h["X-Session-Token"]]["touched"]=time.monotonic()-main.TTL-1
  self.assertEqual(self.c.post("/api/analysis",json=self.body(),headers=self.h).status_code,401)

 def test_retained_job_capacity_preserves_existing_results_and_recovers_after_expiry(self):
  with patch.object(main,"MAX_RETAINED_JOBS",1),patch.object(ai_service,"analyze_instructions",side_effect=ai_service.AnalysisError("service_busy","offline")) as provider:
   first=self.c.post("/api/analysis",json=self.body(),headers=self.h)
   first_id=first.json()["job_id"]
   self.assertEqual(self.wait(first_id)["status"],"failed")
   body=self.body();body["revision"]="next"
   full=self.c.post("/api/analysis",json=body,headers=self.h)
   self.assertEqual(full.status_code,503)
   self.assertEqual(full.json(),{"detail":"job_capacity"})
   self.assertEqual(provider.call_count,1)
   self.assertEqual(self.c.get("/api/jobs/"+first_id,headers=self.h).status_code,200)
   main.jobs[first_id]["created"]=time.monotonic()-main.TTL-1
   retry=self.c.post("/api/analysis",json=body,headers=self.h)
   self.assertEqual(retry.status_code,202)
   self.assertEqual(self.wait(retry.json()["job_id"])["status"],"failed")
   self.assertEqual(provider.call_count,2)
   self.assertEqual(len(main.jobs),1)
   self.assertEqual(self.c.get("/api/jobs/"+first_id,headers=self.h).status_code,404)
 def test_duplicate_and_bounded_global_queue(self):
  import threading
  entered=threading.Event();release=threading.Event()
  def block(*args,**kwargs):
   entered.set();release.wait(5)
   raise ai_service.AnalysisError("service_busy","offline")
  with patch.object(ai_service,"analyze_instructions",side_effect=block):
   first=self.c.post("/api/analysis",json=self.body(),headers=self.h)
   self.assertTrue(entered.wait(1))
   job=first.json()["job_id"]
   try:
    duplicate=self.c.post("/api/analysis",json=self.body(),headers=self.h)
    self.assertEqual(duplicate.json()["job_id"],job)
    different=self.body();different["revision"]="other"
    self.assertEqual(self.c.post("/api/analysis",json=different,headers=self.h).status_code,409)
    for _ in range(2):
     token=self.c.post("/api/session").json()["token"]
     self.assertEqual(self.c.post("/api/analysis",json=self.body(),headers={"X-Session-Token":token}).status_code,202)
    token=self.c.post("/api/session").json()["token"]
    self.assertEqual(self.c.post("/api/analysis",json=self.body(),headers={"X-Session-Token":token}).status_code,429)
   finally:release.set()
   self.wait(job)


 def test_api_runs_real_generation_review_pipeline_with_mocked_transport(self):
  import json,os,httpx
  from google.genai import types
  from request_control import RequestBudget
  from tests.fixtures import SOURCE,payload
  from tests.test_semantic_review import scripted_review
  original=ai_service.check_evidence(ai_service.ProviderAnalysis.model_validate(payload()),SOURCE,source_type="user_provided",source_url=None,model=ai_service.DEFAULT_MODEL)
  review=scripted_review(original,SOURCE,set(ai_service.review_candidates(original)))
  for fail_review in (False,True):
   with self.subTest(fail_review=fail_review):
    requests=[];clock=[0.0];real_client=ai_service.genai.Client
    def respond(request):
     requests.append(json.loads(request.content))
     if len(requests)==2 and fail_review:
      return httpx.Response(503,json={"error":{"code":503,"message":"mocked review failure"}})
     text=json.dumps(wire_payload(payload())) if len(requests)==1 else review.model_dump_json()
     return httpx.Response(200,json={"candidates":[{"content":{"role":"model","parts":[{"text":text}]},"finishReason":"STOP"}]})
    def create_client(**kwargs):
     return real_client(vertexai=False,api_key="offline-test-placeholder",http_options=types.HttpOptions(api_version=ai_service.API_VERSION,retry_options=types.HttpRetryOptions(attempts=1),client_args={"transport":httpx.MockTransport(respond)}))
    with patch.dict(os.environ,{"GEMINI_API_KEY":"offline-test-placeholder"}),patch.object(ai_service.genai,"Client",side_effect=create_client),patch.object(ai_service,"REQUEST_BUDGET",RequestBudget(clock=lambda:clock[0])),patch.object(ai_service,"sleep",side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)):
     body=self.body();body["text"]=SOURCE;body["revision"]="sdk-"+str(fail_review)
     response=self.c.post("/api/analysis",json=body,headers=self.h)
     data=self.wait(response.json()["job_id"])
    self.assertEqual(len(requests),2)
    self.assertEqual(data["status"],"succeeded")
    if fail_review:
     self.assertEqual(data['result']['review_mode'],'deterministic_only')
     self.assertFalse(data['result']['semantic_review_complete'])
    else:
     self.assertTrue(data["result"]["has_guidance"])
     self.assertTrue(data["result"]["evidence"])


 def test_json_body_limit_applies_before_validation(self):
  with patch.object(ai_service,"analyze_instructions") as provider:
   payload=b'{"text":"'+b"x"*(128*1024)+b'"}'
   response=self.c.post("/api/analysis",content=payload,headers={**self.h,"Content-Type":"application/json"})
   self.assertEqual(response.status_code,413)
   self.assertEqual(response.json(),{"detail":"request_too_large"})
   provider.assert_not_called()
 def test_streamed_body_cannot_bypass_limit(self):
  def chunks():
   yield b"x"*70000
   yield b"x"*70000
  response=self.c.post("/api/analysis",content=chunks(),headers={**self.h,"Content-Type":"application/json"})
  self.assertEqual(response.status_code,413)
 def test_confirmation_is_a_strict_boolean(self):
  body=self.body();body["reviewed"]="true"
  with patch.object(ai_service,"analyze_instructions") as provider:
   response=self.c.post("/api/analysis",json=body,headers=self.h)
   self.assertEqual(response.status_code,422)
   provider.assert_not_called()

 def test_api_responses_are_not_cacheable_including_errors(self):
  for response in (self.c.get("/api/health"),self.c.post("/api/session"),self.c.get("/api/jobs/missing",headers=self.h)):
   self.assertIn("no-store",response.headers["cache-control"])
   self.assertEqual(response.headers["x-content-type-options"],"nosniff")
 def test_dangling_claim_cannot_reach_public_result(self):
  _,result=load_example()
  invalid=result.steps[0].model_copy(update=dict(semantic_status="supported",evidence_ids=["e999"]))
  result=result.model_copy(update=dict(semantic_review_complete=True,steps=[invalid]))
  output=main.public_result(result)
  self.assertEqual(output["sections"]["steps"],[])
  self.assertTrue(output["partial"])

if __name__=="__main__": unittest.main()
