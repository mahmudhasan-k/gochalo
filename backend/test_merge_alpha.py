"""Alpha behavior regressions. All providers are mocked or absent."""
import json
from pathlib import Path
import pytest
import ai_service as service
import main
from tests.fixtures import payload, SOURCE, wire_payload
from tests.test_semantic_review import scripted_review


def checked(data=None, source=SOURCE):
    return service.check_evidence(service.ProviderAnalysis.model_validate(data or payload()),source,
        source_type="user_provided",source_url=None,model="offline",output_language="en")


def reviewed(data=None, source=SOURCE):
    result=checked(data,source)
    return service.apply_semantic_review(result,source,
        scripted_review(result,source,set(service.review_candidates(result))),output_language="en")


def test_quote_first_ids_are_deterministic_and_deduplicated_without_rewriting():
    wire=wire_payload(payload())
    schema=service.QuoteFirstAnalysis.model_json_schema()
    assert list(schema["$defs"]["QuoteClaim"]["properties"])[0]=="source_quotes"
    assert "evidence" not in schema["properties"]
    one=service.adapt_quote_first(service.QuoteFirstAnalysis.model_validate(wire))
    two=service.adapt_quote_first(service.QuoteFirstAnalysis.model_validate(wire))
    assert one==two
    assert one.explanation[0].evidence_ids==one.steps[0].evidence_ids==["e1"]
    assert [e.excerpt for e in one.evidence]==[e["excerpt"] for e in payload()["evidence"]]
    assert len(one.evidence)==2


@pytest.mark.parametrize("mutation,reason",[("quotation","quotation_mismatch"),("number","numeric_mismatch")])
def test_invalid_quotes_and_numbers_remain_private_even_under_approval(mutation,reason):
    data=payload()
    if mutation=="quotation":data["evidence"][0]["excerpt"]="Invented source passage."
    else:data["steps"][0]["text"]="Pay 999 taka."
    result=reviewed(data)
    public=main.public_result(result)
    assert not public["sections"]["steps"]
    assert public["section_states"]["steps"]=="unconfirmed"
    assert any(u["category"]=="steps" and u["reason_code"]==reason for u in public["unknowns"])
    assert "Pay 999" not in json.dumps(public)


def test_multiple_independent_document_clauses_allow_complete_local_quote_only():
    local="ঢাকার ক্ষেত্রে জাতীয় পরিচয়পত্রের কপি জমা দিন।"
    other="চট্টগ্রামের ক্ষেত্রে জাতীয় পরিচয়পত্রের কপি দেখান।"
    source=local+" "+other
    good=service.Claim(text=local,evidence_ids=["e1"],status="source_stated")
    bad=good.model_copy(update={"text":"জাতীয় পরিচয়পত্রের কপি জমা দিন।"})
    assert service.scope_withholding_reason(good,"documents",source,local) is None
    assert service.scope_withholding_reason(bad,"documents",source,local)is None
    assert service.scope_withholding_reason(good,"documents",source,other)is None


def test_ambiguous_general_original_rule_cannot_be_bypassed_with_local_quote():
    local="ঢাকার ক্ষেত্রে জাতীয় পরিচয়পত্রের কপি জমা দিন।"
    source=local+" বিদেশের ক্ষেত্রে জাতীয় পরিচয়পত্র অথবা জন্মনিবন্ধন দিন। মূল জাতীয় পরিচয়পত্র জমা দিতে হবে।"
    claim=service.Claim(text=local,evidence_ids=["e1"],status="source_stated")
    assert service.scope_withholding_reason(claim,"documents",source,local)is None


def test_cited_uncertainty_stays_unconfirmed_but_explicit_absence_is_missing():
    result=reviewed()
    public=main.public_result(result)
    assert public["section_states"]["fees"]=="unconfirmed"
    assert not any(u["kind"]=="missing" for u in public["unknowns"])
    data=payload();data["unknowns"]=[dict(kind="missing",category="fees",reason_code="source_absent",text="Fees: Not stated.",evidence_ids=[])]
    public=main.public_result(reviewed(data))
    assert public["section_states"]["fees"]=="not_stated"
    assert any(u["kind"]=="missing" and u["category"]=="fees" for u in public["unknowns"])


def test_incomplete_review_never_establishes_absence_or_claims_semantic_completion():
    data=payload();data["unknowns"]=[dict(kind="missing",category="fees",reason_code="source_absent",text="Fees: Not stated.",evidence_ids=[])]
    result=service.deterministic_review_fallback(checked(data),TimeoutError(),source_text=SOURCE)
    public=main.public_result(result)
    assert public["semantic_review_complete"] is False
    assert public["review_mode"]=="deterministic_only"
    assert public["section_states"]["fees"]=="unconfirmed"
    assert not any(u["kind"]=="missing" for u in public["unknowns"])


def test_withholding_beats_missing_and_omitted_condition_is_not_source_conflict():
    data=payload();data["unknowns"]=[dict(kind="missing",category="documents",reason_code="source_absent",text="Documents: Not stated.",evidence_ids=[])]
    original=checked(data)
    review=scripted_review(original,SOURCE,set(service.review_candidates(original)))
    decision=next(d for d in review.decisions if d.claim_id=="documents:0")
    decision.verdict="contradictory";decision.missing_condition_ids=["e1"]
    result=service.apply_semantic_review(original,SOURCE,review,output_language="en")
    public=main.public_result(result)
    assert public["section_states"]["documents"]=="unconfirmed"
    assert not any(u["kind"]=="contradiction" for u in public["unknowns"])
    assert not any(u["kind"]=="missing" and u["category"]=="documents" for u in public["unknowns"])
    assert any(u["reason_code"]=="missing_conditions" for u in public["unknowns"])


def test_legacy_saved_example_cannot_establish_absence():
    from examples import load_example
    _,result=load_example(output_language="en")
    public=main.public_result(result,demo=True)
    assert "not_stated" not in public["section_states"].values()
    assert not public["semantic_review_complete"]


def test_group_order_and_distinct_conditional_notices_survive():
    result=reviewed()
    result.unknowns=[service.Uncertainty(kind=kind,category=category,reason_code=reason,text=text,evidence_ids=[])
        for kind,category,reason,text in [("missing","fees","source_absent","Conditional fee amount A is absent."),
        ("missing","fees","source_absent","Conditional fee amount B is absent."),
        ("missing","documents","source_absent","Document details are absent."),
        ("contradiction","eligibility","source_conflict","Two eligibility rules conflict."),
        ("unverified","steps","unresolved_scope","Step conditions are unclear.")]]
    public=main.public_result(result)
    assert [(u["kind"],u["category"]) for u in public["unknowns"]]==[("contradiction","eligibility"),("missing","documents"),("missing","deadlines"),("missing","fees"),("missing","fees"),("unverified","steps")]


def test_all_archived_corpus_quotes_still_pass_or_fail_the_original_literal_checks():
    from tests.adversarial_fixtures import corpus
    for case in corpus():
        result=checked(case.model_response,case.source)
        evidence={service.normalize_whitespace(e.excerpt):e for e in result.evidence}
        for quote in case.required_evidence:
            assert evidence[service.normalize_whitespace(quote)].excerpt_found
        for quote in case.rejected_evidence:
            assert not evidence[service.normalize_whitespace(quote)].excerpt_found


def test_default_fee_keeps_first_correction_alternative_in_same_standalone_claim():
    source="সাধারণ ফি ২৩০ টাকা। প্রথমবার জন্মতারিখ সংশোধনের ফি ১০০ টাকা।"
    bad=service.Claim(text="সাধারণ ফি ২৩০ টাকা।",evidence_ids=["e1"],status="source_stated")
    good=bad.model_copy(update={"text":source})
    alternative=bad.model_copy(update={"text":"প্রথমবার জন্মতারিখ সংশোধনের ফি ১০০ টাকা।"})
    assert service.scope_withholding_reason(bad,"fees",source,source)=="fee_exception"
    assert service.scope_withholding_reason(good,"fees",source,source) is None
    assert service.scope_withholding_reason(alternative,"fees",source,source) is None


@pytest.mark.parametrize("text",["Submit certificate A unless already submitted.","Submit certificate B unless already submitted.","Submit certificate A AND certificate B unless already submitted."])
def test_english_or_alternative_cannot_become_independent_mandatory_steps(text):
    source="Submit certificate A OR certificate B unless already submitted."
    item=service.Claim(text=text,evidence_ids=["e1"],status="source_stated")
    assert service.scope_withholding_reason(item,"steps",source,source)=="document_alternative"
    item.text=source
    assert service.scope_withholding_reason(item,"steps",source,source) is None


def test_english_global_eligibility_is_retained_in_every_standalone_action():
    scope="Only current students who live in this district may apply."
    source=scope+" Submit the application form even when exempt from fees."
    item=service.Claim(text="Submit the application form.",evidence_ids=["e1"],status="source_stated")
    assert service.scope_withholding_reason(item,"steps",source,source)=="global_scope"
    item.text="For current students who live in this district, submit the application form even when exempt from fees."
    assert service.scope_withholding_reason(item,"steps",source,source) is None


def test_wrong_english_review_approval_cannot_override_known_scope_failures():
    source="Only current students who live in this district may apply. Submit certificate A OR certificate B unless already submitted."
    data=payload();data['evidence']=[dict(id='e1',excerpt=source)]
    data['explanation']=[dict(text="Only current students who live in this district may apply.",evidence_ids=['e1'],status='source_stated')]
    data['steps']=[dict(text="Submit certificate A unless already submitted.",evidence_ids=['e1'],status='source_stated'),dict(text="Submit certificate B unless already submitted.",evidence_ids=['e1'],status='source_stated')]
    data['documents']=[]
    public=main.public_result(reviewed(data,source))
    assert public['sections']['steps']==[]
    assert any(u['category']=='steps' and u['reason_code']=='missing_conditions' for u in public['unknowns'])


@pytest.mark.parametrize("text",[
 "শুধুমাত্র নির্দিষ্ট জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে, আবেদনপত্রে নিজের সচল মোবাইল নম্বর লিখুন।",
 "এই জেলায় বসবাসকারী বর্তমান শিক্ষার্থী হলে সচল মোবাইল নম্বর লিখুন।",
 "For current students living in this district, enter a working mobile number.",
 "If you live in this district and are currently a student, enter a working mobile number.",
])
def test_complete_known_eligibility_paraphrases_are_not_deleted(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'steps',P1['source']) is None


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা অথবা বর্তমানে শিক্ষার্থী হলে সচল মোবাইল নম্বর লিখুন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী না হলে সচল মোবাইল নম্বর লিখুন।",
 "For current students living in this district or applicants from elsewhere, enter a number.",
 "For not current students living in this district, enter a number.",
 "For current students, enter a number.",
])
def test_omitted_negated_or_broadened_eligibility_stays_withheld(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'steps',P1['source'])=='global_scope'


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে প্রতিবন্ধী না হলে ২০০ টাকা ফি দিন।",
 "For current students living in this district, pay ২০০ taka unless you are disabled.",
])
def test_known_disability_exemption_paraphrases_keep_both_global_and_local_scope(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'fees',P1['source']) is None


def test_bangla_combining_marks_do_not_turn_nomuna_into_standalone_negation():
    from tests.test_semantic_review import P1
    text="এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—উভয় শর্ত পূরণকারী আবেদনকারীদের জন্য নমুনা নিবন্ধন।"
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'explanation',P1['source']) is None
    claim.text="এই জেলার বাসিন্দা অথবা বর্তমানে শিক্ষার্থী হলে নমুনা নিবন্ধন।"
    assert service.scope_withholding_reason(claim,'explanation',P1['source'])=='global_scope'


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—উভয় শর্ত পূরণকারী আবেদনকারীরা আবেদনপত্রে নিজের সচল মোবাইল নম্বর লিখুন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—দুটি শর্তই পূরণ হলে নিজের সচল মোবাইল নম্বর লিখুন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—উভয় শর্ত পূরণকারী আবেদনকারীরা, আগে সনদ জমা না দিয়ে থাকলে, শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",
])
def test_explicit_both_conditions_noun_phrase_does_not_require_one_literal_suffix(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'steps',P1['source']) is None


def test_review_timeout_cannot_bypass_the_shared_alternative_scope_guard():
    source="Submit certificate A OR certificate B unless already submitted."
    data=payload();data['evidence']=[dict(id='e1',excerpt=source)]
    data['explanation']=[dict(text=source,evidence_ids=['e1'],status='source_stated')]
    data['steps']=[dict(text="Submit certificate A unless already submitted.",evidence_ids=['e1'],status='source_stated')]
    data['documents']=[]
    degraded=service.deterministic_review_fallback(checked(data,source),TimeoutError(),source_text=source)
    public=main.public_result(degraded)
    assert public['sections']['steps']==[]
    assert public['sections']['explanation']
    assert public['review_mode']=='deterministic_only'
    assert not public['semantic_review_complete']


@pytest.mark.parametrize("text",[
 "শুধুমাত্র এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—এই দুটি শর্ত পূরণকারী আবেদনকারীরা আবেদনপত্রে নিজের সচল মোবাইল নম্বর লিখুন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী এমন আবেদনকারীরা ফি না লাগলেও আবেদনপত্র জমা দিন।",
 "প্রতিবন্ধী নন এমন আবেদনকারীরা, যারা এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী, তারা ২০০ টাকা ফি দিন।",
])
def test_full_affirmative_eligibility_does_not_require_a_particular_grammatical_ending(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'steps',P1['source']) is None


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী নন এমন আবেদনকারীরা আবেদন করুন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী—এই দুটি শর্ত পূরণ না করলেও আবেদন করুন।",
 "এই জেলার বাসিন্দা অথবা বর্তমানে শিক্ষার্থী এমন আবেদনকারীরা আবেদন করুন।",
])
def test_affirmative_core_cannot_be_followed_by_negation_or_nonfulfillment(text):
    from tests.test_semantic_review import P1
    claim=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(claim,'steps',P1['source'])=='global_scope'


def test_equivalent_english_condition_is_admitted_but_extra_source_qualification_is_not_dropped():
    item=service.Claim(text="For current students living in this district, submit the form.",evidence_ids=['e1'],status='source_stated')
    source="Only current students who live in this district may apply. Submit the form."
    assert service.scope_withholding_reason(item,'steps',source,source) is None
    extended="Only current students who live in this district and have paid tuition may apply. Submit the form."
    assert service.scope_withholding_reason(item,'steps',extended,extended)=='global_scope'


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে, যদি আগে সনদ জমা না দিয়ে থাকেন, তবে শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে, আগে সনদ জমা না দিয়ে থাকলে শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",
])
def test_negative_prior_submission_condition_keeps_equivalent_conditional_forms(text):
    from tests.test_semantic_review import P1
    item=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(item,'documents',P1['source']) is None


@pytest.mark.parametrize("text",[
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",
 "এই জেলার বাসিন্দা এবং বর্তমানে শিক্ষার্থী হলে আগে সনদ জমা দিয়ে থাকলে শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",
])
def test_omitted_or_reversed_prior_submission_condition_remains_withheld(text):
    from tests.test_semantic_review import P1
    item=service.Claim(text=text,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(item,'documents',P1['source'])=='prior_submission'


def test_exact_attached_conditions_preserve_global_and_local_scope_without_rephrasing():
    from tests.test_semantic_review import P1
    global_clause=next(service._GLOBAL_PAIR.finditer(P1['source'])).group()
    prior="আগে সনদ জমা না দিয়ে থাকলে শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন; দুটোই লাগবে না।"
    item=service.Claim(text="শিক্ষার্থী সনদ অথবা প্রতিষ্ঠানের প্রত্যয়নপত্র দিন।",source_conditions=[global_clause,prior],evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(item,'documents',P1['source'],P1['source']) is None
    item.text="আবেদনপত্র জমা দিন।"
    assert service.scope_withholding_reason(item,'steps',P1['source'],P1['source'])=='local_condition_leak'


def test_attached_context_cannot_mask_reversed_eligibility_or_split_alternatives():
    source="Only current students who live in this district may apply. Submit certificate A OR certificate B unless already submitted."
    context=["Only current students who live in this district may apply."]
    item=service.Claim(text="For not current students, submit certificate A OR certificate B.",source_conditions=context,evidence_ids=['e1'],status='source_stated')
    assert service.scope_withholding_reason(item,'steps',source,source)=='global_scope'
    item.text="Submit certificate A unless already submitted."
    assert service.scope_withholding_reason(item,'steps',source,source)=='document_alternative'


def test_quote_adapter_attaches_only_explicit_original_global_conditions_and_assigns_ids():
    source="Only current students who live in this district may apply. Submit the form."
    wire=wire_payload(payload());wire['explanation']=[dict(source_quotes=[source],source_conditions=[],text="Current students may apply.",status='source_stated')]
    wire['steps']=[dict(source_quotes=["Submit the form."],source_conditions=[],text="Submit the form.",status='source_stated')];wire['documents']=[]
    adapted=service.adapt_quote_first(service.QuoteFirstAnalysis.model_validate(wire),source)
    assert adapted.steps[0].source_conditions==["Only current students who live in this district may apply."]
    assert len(adapted.steps[0].evidence_ids)==2


def test_unmatched_or_uncited_condition_cannot_reach_public_output():
    data=payload();data['steps'][0]['source_conditions']=['Invented applicant group.']
    result=reviewed(data)
    assert not main.public_result(result)['sections']['steps']
    good=reviewed();good.steps[0].source_conditions=['Invented applicant group.']
    assert not main.public_result(good)['sections']['steps']

def test_same_notice_with_distinct_evidence_is_not_collapsed():
    result=reviewed()
    result.unknowns=[service.Uncertainty(kind='unverified',category='fees',reason_code='unresolved_scope',text='Fee applicability is unclear.',evidence_ids=[ref]) for ref in ('e1','e2')]
    public=main.public_result(result)
    notices=[u for u in public['unknowns'] if u['text']=='Fee applicability is unclear.']
    assert len(notices)==2
    assert {tuple(u['evidence_ids']) for u in notices}=={('e1',),('e2',)}
