"""Offline bootstrapping and cross-origin boundaries for split hosting."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import ai_service
from examples import load_example


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        environment=patch.dict(os.environ,{
            "APP_ENV":"production",
            "FRONTEND_ORIGINS":" https://pages.example/ , https://preview.example ",
        })
        environment.start();self.addCleanup(environment.stop)
        # Load the actual startup code with isolated job/session/middleware state.
        name="_deployment_test_app"
        spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name("main.py"))
        self.module=importlib.util.module_from_spec(spec)
        sys.modules[name]=self.module
        self.addCleanup(sys.modules.pop,name,None)
        spec.loader.exec_module(self.module)
        self.client=TestClient(self.module.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__,None,None,None)

    def test_allowed_frontends_can_preflight_token_authenticated_requests(self):
        with patch.object(ai_service,"analyze_instructions") as provider:
            for origin in ("https://pages.example","https://preview.example"):
                response=self.client.options("/api/analysis",headers={
                    "Origin":origin,"Access-Control-Request-Method":"POST",
                    "Access-Control-Request-Headers":"content-type,x-session-token",
                })
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers["access-control-allow-origin"],origin)
                self.assertIn("x-session-token",response.headers["access-control-allow-headers"].lower())
                self.assertNotIn("access-control-allow-credentials",response.headers)
                self.assertIn("Origin",response.headers["vary"])
            provider.assert_not_called()

    def test_unlisted_origins_and_methods_cannot_gain_browser_read_access(self):
        for origin in ("https://pages.example.evil","http://pages.example","https://unlisted.example","null"):
            with self.subTest(origin=origin):
                headers={"Origin":origin,"Access-Control-Request-Method":"POST"}
                self.assertEqual(self.client.options("/api/session",headers=headers).status_code,400)
                response=self.client.get("/api/health",headers={"Origin":origin})
                self.assertNotIn("access-control-allow-origin",response.headers)
        response=self.client.options("/api/analysis",headers={
            "Origin":"https://pages.example","Access-Control-Request-Method":"DELETE",
        })
        self.assertEqual(response.status_code,400)

    def test_allowed_origin_receives_safe_errors_and_private_authenticated_stream(self):
        origin={"Origin":"https://pages.example"}
        response=self.client.post("/api/analysis",headers=origin,json={"text":"PRIVATE_INVALID"})
        self.assertEqual(response.status_code,422)
        self.assertEqual(response.headers["access-control-allow-origin"],origin["Origin"])
        self.assertIn("no-store",response.headers["cache-control"])
        self.assertNotIn("PRIVATE_INVALID",response.text)
        token=self.client.post("/api/session",headers=origin).json()["token"]
        headers={**origin,"X-Session-Token":token}
        _,result=load_example()
        result=result.model_copy(update={"semantic_review_complete":True})
        with patch.object(ai_service,"analyze_instructions",return_value=result) as provider:
            job=self.client.post("/api/analysis",headers=headers,json={
                "text":"Public fixture","kind":"text","reviewed":True,"revision":"split-host",
            }).json()["job_id"]
            stream=self.client.get(f"/api/jobs/{job}/stream",headers=headers)
            self.assertEqual(stream.status_code,200)
            self.assertEqual(stream.headers["access-control-allow-origin"],origin["Origin"])
            self.assertIn("text/event-stream",stream.headers["content-type"])
            self.assertIn("no-store",stream.headers["cache-control"])
            self.assertEqual(stream.headers["x-accel-buffering"],"no")
            self.assertIn('"stage": "completed"',stream.text)
            self.assertEqual(self.client.get(f"/api/jobs/{job}/stream",headers=origin).status_code,401)
            provider.assert_called_once()
