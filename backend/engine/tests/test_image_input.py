"""Offline image validation and shared review workflow; local OCR uses no Gemini allowance."""

from io import BytesIO
import json
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

import ai_service as service
from image_input import MAX_IMAGE_BYTES, prepare_image
from request_control import RequestBudget
from tests.fixtures import SOURCE, payload


def image_bytes(fmt="PNG", size=(80, 40), **kwargs):
    output = BytesIO()
    Image.new("RGB", size, "white").save(output, format=fmt, **kwargs)
    return output.getvalue()


class ImageValidationTests(unittest.TestCase):
    def test_png_jpeg_content_and_metadata_removal(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "PRIVATE")
        for fmt, name, options in (("PNG", "notice.PNG", {"pnginfo": metadata}),
                                   ("JPEG", "notice.jpeg", {"comment": b"PRIVATE"})):
            with self.subTest(fmt=fmt):
                prepared, mime = prepare_image(image_bytes(fmt, **options), name)
                self.assertEqual(mime, "image/png" if fmt == "PNG" else "image/jpeg")
                self.assertNotIn(b"PRIVATE", prepared)
                with Image.open(BytesIO(prepared)) as image:
                    self.assertEqual(image.size, (80, 40))

    def test_rejects_oversize_spoofed_corrupt_unsupported_and_animated_files(self):
        output = BytesIO()
        Image.new("RGB", (8, 8)).save(output, format="PNG", save_all=True,
                                    append_images=[Image.new("RGB", (8, 8), "white")], duration=100)
        cases = [(b"", "a.png", "image_size"), (b"x" * (MAX_IMAGE_BYTES + 1), "a.jpg", "image_size"),
                 (image_bytes(), "a.jpg", "image_invalid"), (b"PRIVATE", "a.png", "image_invalid"),
                 (image_bytes(), "a.pdf", "image_invalid"), (output.getvalue(), "a.png", "image_invalid"),
                 (image_bytes()[:40], "a.png", "image_invalid")]
        for data, name, code in cases:
            with self.subTest(name=name, code=code), self.assertRaises(service.AnalysisError) as caught:
                prepare_image(data, name)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_dimension_and_pixel_limits(self):
        for size in ((6001, 1), (4000, 3001)):
            with self.subTest(size=size), self.assertRaises(service.AnalysisError) as caught:
                prepare_image(image_bytes(size=size), "a.png")
            self.assertEqual(caught.exception.code, "image_dimensions")


# v2 UI contracts live in frontend/src/App.test.tsx. These checks exercise the
# corresponding API boundaries; no Streamlit app or fake UI harness is retained.
import time
import threading
from fastapi.testclient import TestClient
import main
from examples import load_example

class ImageWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__,None,None,None)
        self.headers={"X-Session-Token":self.client.post("/api/session").json()["token"]}

    def extract(self,data=None,revision="image",request_id=""):
        return self.client.post("/api/extract/image",params={"revision":revision,"request_id":request_id},
            content=image_bytes() if data is None else data,headers={**self.headers,"Content-Type":"image/png"})

    def done(self,response):
        self.assertEqual(response.status_code,202)
        job=response.json()["job_id"]
        for _ in range(200):
            snapshot=self.client.get(f"/api/jobs/{job}",headers=self.headers).json()
            if snapshot["status"] in {"succeeded","failed"}:return snapshot
            time.sleep(.005)
        self.fail("Image job did not finish")

    def test_extraction_allows_automatic_analysis_with_truthful_review_metadata(self):
        _,checked=load_example()
        checked=checked.model_copy(update={"semantic_review_complete":True})
        with patch.object(main,"extract_image_text",return_value=SOURCE) as extract,patch.object(service,"analyze_instructions",return_value=checked) as analyze:
            result=self.done(self.extract())
            self.assertEqual(result["result"]["text"],SOURCE)
            extract.assert_called_once();analyze.assert_not_called()
            response=self.client.post("/api/analysis",headers=self.headers,json={"text":SOURCE,"reviewed":False,"kind":"image","revision":"image"})
            result=self.done(response)
            self.assertEqual(result["status"],"succeeded")
            self.assertFalse(result["result"]["source_reviewed"])
            self.assertTrue(result["result"]["semantic_review_complete"])
            analyze.assert_called_once_with(SOURCE,output_language="bn")

    def test_corrupt_upload_fails_before_configuration_budget_or_provider(self):
        with patch.object(main,"extract_image_text") as extract,patch.object(service,"load_settings") as settings,patch.object(service,"REQUEST_BUDGET") as budget:
            response=self.extract(b"corrupt")
            self.assertEqual(response.status_code,400)
            self.assertEqual(response.json()["detail"],"image_invalid")
            extract.assert_not_called();settings.assert_not_called();budget.reserve.assert_not_called()
            self.assertIsNone(main.sessions[self.headers["X-Session-Token"]]["active"])

    def test_failed_extraction_is_sanitized_and_recovery_requires_explicit_request(self):
        with patch.object(main,"extract_image_text",side_effect=[service.AnalysisError("service_busy","PRIVATE"),SOURCE]) as extract:
            failed=self.done(self.extract(revision="first"))
            self.assertEqual(failed["status"],"failed")
            self.assertNotIn("PRIVATE",str(failed))
            self.assertEqual(extract.call_count,1)
            self.client.get("/api/health")
            self.assertEqual(extract.call_count,1)
            recovered=self.done(self.extract(revision="second"))
            self.assertEqual(recovered["result"]["text"],SOURCE)
            self.assertEqual(extract.call_count,2)

    def test_correction_and_output_language_reach_analysis_without_reextracting(self):
        _,result=load_example(output_language="en")
        result=result.model_copy(update={"semantic_review_complete":True})
        corrected=SOURCE+" Corrected text."
        with patch.object(main,"extract_image_text",return_value=SOURCE) as extract,patch.object(service,"analyze_instructions",return_value=result) as analyze:
            self.done(self.extract())
            response=self.client.post("/api/analysis",headers=self.headers,json={"text":corrected,"reviewed":True,"kind":"image","language":"en","revision":"corrected"})
            self.assertEqual(self.done(response)["status"],"succeeded")
            analyze.assert_called_once_with(corrected,output_language="en")
            extract.assert_called_once()

    def test_busy_session_blocks_other_image_work_but_retry_reuses_same_job(self):
        release=threading.Event();entered=threading.Event()
        def work(*args):
            entered.set();release.wait(2);return SOURCE
        with patch.object(main,"extract_image_text",side_effect=work) as extract:
            try:
                first=self.extract(request_id="image-id")
                self.assertTrue(entered.wait(1))
                duplicate=self.extract(request_id="image-id")
                self.assertEqual(duplicate.json()["job_id"],first.json()["job_id"])
                blocked=self.extract(image_bytes(size=(81,40)),revision="other")
                self.assertEqual(blocked.status_code,409)
            finally:release.set()
            self.assertEqual(self.done(first)["status"],"succeeded")
            extract.assert_called_once()

    def test_image_job_is_private_and_completed_reads_do_not_dispatch(self):
        with patch.object(main,"extract_image_text",return_value=SOURCE) as extract:
            response=self.extract();snapshot=self.done(response);job=response.json()["job_id"]
            other={"X-Session-Token":self.client.post("/api/session").json()["token"]}
            self.assertEqual(self.client.get(f"/api/jobs/{job}",headers=other).status_code,404)
            self.assertEqual(self.client.get(f"/api/jobs/{job}",headers=self.headers).json(),snapshot)
            extract.assert_called_once()
