"""Demo resilience regressions; provider transports are mocked/offline."""
import copy

import pytest
from pydantic import ValidationError

import ai_service as ai
import research
import main
import json
from types import SimpleNamespace
from google.genai import errors, types
from tests.fixtures import SOURCE, payload, wire_payload
from ocr_service import ImageTranscription
from schema_utils import strip_grammar_bounds
from source_inventory import Inventory


@pytest.mark.parametrize('language',['en','bn'])
@pytest.mark.parametrize('section',['explanation','fees','deadlines'])
def test_informational_sources_have_guidance_and_clear_missing_categories(language,section):
    from result_metadata import source_absence_notice
    from result_contract import ORDER
    source='The Banned Community presents Banned Beats. Ticket price is 350 BDT. Event date is 10 October 2026.'
    text={'explanation':'The Banned Community presents Banned Beats.',
          'fees':'Ticket price is 350 BDT.','deadlines':'Event date is 10 October 2026.'}[section]
    row=ai.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    data=ai.ProviderAnalysis(explanation=[row] if section=='explanation' else [ai.Claim(text=source,evidence_ids=['e1'],status='source_stated')],steps=[],documents=[],
        fees_and_deadlines=ai.FeesAndDeadlines(fees=[row] if section=='fees' else [],deadlines=[row] if section=='deadlines' else []),
        evidence=[ai.Evidence(id='e1',excerpt=source)],unknowns=[])
    result=ai.check_evidence(data,source,source_type='user_provided',source_url=None,model=ai.DEFAULT_MODEL,output_language=language)
    if section=='explanation':
        result=result.model_copy(update={'explanation':[r.model_copy(update={'semantic_status':'supported'}) for r in result.explanation]})
    else:
        timing=result.fees_and_deadlines.model_copy(update={section:[r.model_copy(update={'semantic_status':'supported'}) for r in getattr(result.fees_and_deadlines,section)]})
        result=result.model_copy(update={'fees_and_deadlines':timing,'explanation':[]})
    public=main.public_result(result.model_copy(update={'semantic_review_complete':True}))
    assert public['has_guidance'] is True and public['category_order']==list(ORDER)
    assert set(public['sections'])=={'explanation','steps','documents','fees','deadlines'}
    for category in {'steps','documents','fees','deadlines'}-{section}:
        notices=[u for u in public['unknowns'] if u['category']==category and u['kind']=='missing']
        assert len(notices)==1
        assert notices[0]==source_absence_notice(category,language)


def test_only_unknowns_do_not_count_as_guidance():
    from result_contract import finalize
    output={'review_mode':'ai_reviewed','sections':{k:[] for k in ('explanation','steps','documents','fees','deadlines')},
        'evidence':[],'unknowns':[],'section_states':{}}
    assert finalize(output)['has_guidance'] is False


def test_schema_projection_preserves_property_names_references_and_local_validation():
    for model in (ai.SemanticReview, ai.QuoteFirstAnalysis, ai.AskPlan, ImageTranscription, research.ResearchPlan, Inventory):
        original = model.model_json_schema()
        snapshot = copy.deepcopy(original)
        projected = strip_grammar_bounds(original)
        assert original == snapshot
        assert projected.get('required') == original.get('required')
        assert set(projected.get('properties', {})) == set(original.get('properties', {}))
        def check(schema):
            if not isinstance(schema, dict):
                return
            assert not set(schema) & {'minItems', 'maxItems', 'minLength', 'maxLength', 'default', 'title'}
            for key, value in schema.items():
                if key in {'properties', '$defs'}:
                    for child in value.values(): check(child)
                elif isinstance(value, dict): check(value)
                elif isinstance(value, list):
                    for child in value: check(child)
        check(projected)
    assert 'title' in strip_grammar_bounds(research.ResearchPlan.model_json_schema())['properties']
    with pytest.raises(ValidationError):
        ImageTranscription.model_validate({'text': 'x' * 10_001})
    with pytest.raises(ValidationError):
        ai.SemanticReview.model_validate({'evidence': [], 'decisions': [], 'omissions': [
            {'category': 'general', 'source_quote': 'x'}] * 81})


def test_schema_projection_does_not_remove_real_fields_named_like_keywords():
    schema = {'title': 'Annotation', 'type': 'object', 'properties': {
        'title': {'title': 'Field annotation', 'type': 'string', 'maxLength': 160},
        'default': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string'}}},
        'required': ['title', 'default'], 'additionalProperties': False}
    assert strip_grammar_bounds(schema) == {'type': 'object', 'properties': {
        'title': {'type': 'string'}, 'default': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['title', 'default'], 'additionalProperties': False}


@pytest.mark.parametrize('failure',[400,429,500,502,503,504,'malformed','value','timeout','validation'])
def test_any_review_failure_returns_only_locally_admitted_unreviewed_claims(monkeypatch,failure):
    calls=[]
    monkeypatch.setenv('GEMINI_API_KEY','offline-only')
    def generate(*args,**kwargs):
        calls.append(kwargs)
        if kwargs['stage']=='semantic_review':
            assert kwargs['config'].thinking_config is None
            if isinstance(failure,int):raise errors.APIError(failure,{'error':{'code':failure,'message':'PRIVATE'}})
            if failure=='malformed':raise ai.AnalysisError('malformed_response','safe')
            if failure=='value':raise ValueError('PRIVATE')
            if failure=='timeout':raise TimeoutError('PRIVATE')
            ai.SemanticReview.model_validate({'evidence':'invalid','decisions':[]})
        return SimpleNamespace(text=json.dumps(wire_payload(payload())),candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)])
    monkeypatch.setattr(ai,'gemini_generate',generate)
    result=ai.analyze_instructions(SOURCE)
    public=main.public_result(result)
    assert public['review_mode']=='deterministic_only' and public['semantic_review_complete'] is False
    assert public['has_guidance'] and public['evidence']
    assert [c['stage'] for c in calls]==['source_generation','semantic_review']
    assert 'PRIVATE' not in json.dumps(public)
    supported={e['id'] for e in public['evidence']}
    assert all(set(row['evidence_ids'])<=supported for rows in public['sections'].values() for row in rows)


def test_generation_failure_still_exposes_no_draft(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','offline-only')
    monkeypatch.setattr(ai,'gemini_generate',lambda *a,**k:(_ for _ in ()).throw(ai.AnalysisError('provider_error','safe')))
    with pytest.raises(ai.AnalysisError):ai.analyze_instructions(SOURCE)


def test_long_source_inventory_failure_preserves_full_source_for_generation(monkeypatch):
    import source_inventory
    source=SOURCE+'\n'+'Long source padding. '*600
    calls=[]
    monkeypatch.setenv('GEMINI_API_KEY','offline-only')
    monkeypatch.setattr(source_inventory,'extract_inventory',lambda *a,**k:(_ for _ in ()).throw(ValueError('bad inventory')))
    def generate(*args,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=json.dumps(wire_payload(payload())),candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)])
    monkeypatch.setattr(ai,'gemini_generate',generate)
    monkeypatch.setattr(ai,'review_semantics',lambda result,*a,**k:result)
    ai.analyze_instructions(source)
    assert json.loads(calls[0]['contents'])['source_text']==source


def test_fragment_normalization_and_extraction_pacing_keep_security_guards():
    import url_input
    assert url_input.normalize_url('https://example.org/guide?q=1#section')=='https://example.org/guide?q=1'
    clock=[0.0];budget=url_input.ExtractionBudget(clock=lambda:clock[0])
    for second in range(0,30,2):
        clock[0]=second;budget.reserve(url_input.ExtractionSession())
    clock[0]=59.9
    with pytest.raises(url_input.ExtractionError):budget.reserve(url_input.ExtractionSession())
    clock[0]=60;budget.reserve(url_input.ExtractionSession())
    with pytest.raises(url_input.ExtractionError):url_input.normalize_url('https://127.0.0.1/private#ignored')
