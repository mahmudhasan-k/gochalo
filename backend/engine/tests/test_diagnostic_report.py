import io
import json
from pathlib import Path
import tempfile
import unittest

from google.genai import errors

import ai_service as service
from diagnostic_report import console_report, write_safe_report
from tests.test_quality import checked


class DiagnosticReportTests(unittest.TestCase):
    def test_windows_cp1252_console_and_utf8_file(self):
        diagnostic = service.provider_diagnostics(
            errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "PRIVATE SOURCE"}}),
            model=service.DEFAULT_MODEL,
        )
        # Exercise Unicode even though current allowlisted error summaries use English.
        diagnostic = diagnostic.model_copy(update={"message": "নিরাপদ পরীক্ষার বার্তা"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            rendered = write_safe_report(diagnostic, path)
            saved = path.read_text(encoding="utf-8")
        self.assertIn("নিরাপদ", saved)
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252")
        stream.write(rendered)
        stream.flush()
        self.assertEqual(json.loads(buffer.getvalue().decode("cp1252")), json.loads(saved))
        self.assertEqual(rendered, console_report(diagnostic))

    def test_success_exports_counts_without_source_claims_or_urls(self):
        result = checked().model_copy(update={"source_url": "https://private.example/secret"})
        rendered = console_report(result)
        self.assertEqual(json.loads(rendered)["missing_notice_count"], 0)
        self.assertEqual(json.loads(rendered)["matched_evidence_count"], 2)
        self.assertNotIn("private.example", rendered)
        self.assertNotIn(result.explanation[0].text, rendered)
        self.assertNotIn("excerpt", rendered)

    def test_raw_objects_and_provider_errors_are_rejected(self):
        for raw in ({"api_key": "SECRET", "source": "PRIVATE"}, RuntimeError("PRIVATE")):
            with self.assertRaises(TypeError):
                console_report(raw)

    def test_raw_provider_message_is_not_exported(self):
        diagnostic = service.provider_diagnostics(
            errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "PRIVATE SOURCE AND SECRET"}}),
            model=service.DEFAULT_MODEL,
        )
        rendered = console_report(diagnostic)
        self.assertNotIn("PRIVATE", rendered)
        self.assertNotIn("SECRET", rendered)
        self.assertEqual(json.loads(rendered)["http_status"], 400)
