"""Opt-in local reports: UTF-8 files, ASCII-safe console text, no source bodies."""

import json
from pathlib import Path
import re

from ai_service import AnalysisResult, ProviderDiagnostics


def _safe_payload(report: AnalysisResult | ProviderDiagnostics) -> dict[str, object]:
    if isinstance(report, ProviderDiagnostics):
        # Only pass diagnostics already produced by provider_diagnostics(), never
        # a raw provider exception, raw response, or arbitrary dictionary.
        return report.model_dump()
    if not isinstance(report, AnalysisResult):
        raise TypeError("Only validated analysis or sanitized provider diagnostics are accepted")
    claims = report.explanation + report.steps + report.documents + report.fees_and_deadlines.fees + report.fees_and_deadlines.deadlines
    model = report.model if re.fullmatch(r"(?:models/)?(?:gemini|gemma)-[a-z0-9.-]+", report.model) else "[configured model omitted]"
    return {
        "model": model,
        "section_count": 6,
        "claim_count": len(claims),
        "quotation_matched_claim_count": sum(item.evidence_status == "quotation_matched" for item in claims),
        "unsupported_claim_count": sum(item.evidence_status == "unsupported" for item in claims),
        "contradictory_claim_count": sum(item.evidence_status == "contradictory" for item in claims),
        "missing_notice_count": sum(item.kind == "missing" for item in report.unknowns),
        "unverified_notice_count": sum(item.kind == "unverified" for item in report.unknowns),
        "contradiction_notice_count": sum(item.kind == "contradiction" for item in report.unknowns),
        "evidence_count": len(report.evidence),
        "matched_evidence_count": sum(item.excerpt_found for item in report.evidence),
    }


def console_report(report: AnalysisResult | ProviderDiagnostics) -> str:
    """ASCII JSON can be printed through Windows cp1252 without an encode error."""
    return json.dumps(_safe_payload(report), ensure_ascii=True, indent=2)


def write_safe_report(report: AnalysisResult | ProviderDiagnostics, destination: Path) -> str:
    """Explicit export only; never called automatically during user analysis.

    Successful results export aggregate counts, not claim text, excerpts, URLs or
    user input. Error reports accept the existing allowlisted diagnostics type.
    Return ASCII-safe console text after writing a readable UTF-8 JSON file.
    """
    payload = _safe_payload(report)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json.dumps(payload, ensure_ascii=True, indent=2)
