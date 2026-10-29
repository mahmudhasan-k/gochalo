"""Saved official-source excerpt; quotation validation is not live verification."""
from pathlib import Path
from typing import Literal
from pydantic import ValidationError
from ai_service import StrictModel,Text,ProviderAnalysis,check_evidence,AnalysisError

PATH=Path(__file__).parent/"sources/epassport.json"
class OfficialExample(StrictModel):
    title_bn:Text
    source_url:Literal["https://www.epassport.gov.bd/instructions/instructions"]
    saved_on:Literal["2026-10-21"]
    source_text:Text
    analysis:ProviderAnalysis

def load_official_example(*,output_language="bn"):
    if output_language not in {"bn","en"}:
        return None
    try:
        source=OfficialExample.model_validate_json(PATH.read_text(encoding="utf-8"))
        analysis=source.analysis
        if output_language=="en":
            # The English wording is curated for this exact, one-sentence excerpt.
            if source.source_text!="ই-পাসপোর্টের আবেদনপত্র অনলাইনে পূরণ করা যাবে।":
                return None
            data=analysis.model_dump()
            data["explanation"][0]["text"]="The e-passport application form can be completed online."
            data["steps"][0]["text"]="Complete the e-passport application form online."
            data["unknowns"][0]["text"]="This example covers a single sentence. Consult the original government instructions for eligibility, later steps and current requirements."
            analysis=ProviderAnalysis.model_validate(data)
        result=check_evidence(analysis,source.source_text,source_type="curated_example",
            source_url=source.source_url,model="Saved official-source excerpt",output_language=output_language)
        claims=result.explanation+result.steps+result.documents+result.fees_and_deadlines.fees+result.fees_and_deadlines.deadlines
        if not result.evidence or any(not e.excerpt_found for e in result.evidence) or any(c.evidence_status!="quotation_matched" for c in claims):
            return None
        return source,result
    except (OSError,UnicodeError,ValidationError,AnalysisError,IndexError,KeyError):
        return None
