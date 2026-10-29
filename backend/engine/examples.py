"""Hand-authored fictional demonstration, checked by the same evidence validator."""
from pathlib import Path
from typing import Literal
from pydantic import ValidationError
from ai_service import AnalysisError, AnalysisResult, Claim, ProviderAnalysis, StrictModel, Text, check_evidence

EXAMPLE_PATH = Path(__file__).parent / "sources/example.json"

class CuratedExample(StrictModel):
    fictional: Literal[True]
    title_bn: Text
    title_en: Text
    saved_on: str
    source_text: Text
    analyses: dict[str, ProviderAnalysis]
    student_explanation: dict[str, Claim]


def load_example(path=EXAMPLE_PATH, *, output_language="bn", audience="general") -> tuple[CuratedExample, AnalysisResult] | None:
    try:
        example = CuratedExample.model_validate_json(Path(path).read_text(encoding="utf-8"))
        analysis = example.analyses[output_language]
        if audience == "student":
            analysis = analysis.model_copy(update={"explanation": [example.student_explanation[output_language]]})
        elif audience != "general":
            return None
        result = check_evidence(analysis, example.source_text,
                                source_type="curated_example", source_url=None,
                                model="Hand-authored fictional example", output_language=output_language)
        claims = result.explanation + result.steps + result.documents + result.fees_and_deadlines.fees + result.fees_and_deadlines.deadlines
        if not result.evidence or not all(item.excerpt_found for item in result.evidence):
            return None
        if any(item.evidence_status != "quotation_matched" for item in claims):
            return None
        return example, result
    except (OSError, UnicodeError, KeyError, ValidationError, AnalysisError):
        return None
