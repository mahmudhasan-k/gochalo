"""Application-owned uncertainty presentation; never expose rejected advice."""
from i18n import NOTICES

ORDER = ("documents", "deadlines", "fees", "eligibility", "steps", "general")
KINDS = {"contradiction": 0, "missing": 1, "unverified": 2}
LABELS = {
    "bn": {"documents":"কাগজপত্র", "deadlines":"সময় ও তারিখ", "fees":"ফি", "eligibility":"আবেদনের যোগ্যতা", "steps":"করণীয়", "general":"অন্যান্য তথ্য"},
    "en": {"documents":"Documents", "deadlines":"Dates and timeframes", "fees":"Fees", "eligibility":"Eligibility", "steps":"Actions", "general":"Other information"},
}
TEXT = {
    "bn": {"source_absent":"{label}: এই তথ্যটি দেওয়া উৎসে উল্লেখ নেই।", "quotation_mismatch":"{label}: উৎসের উদ্ধৃতির সঙ্গে মেলানো যায়নি।", "numeric_mismatch":"{label}: সংখ্যার তথ্য উৎসের সঙ্গে মেলানো যায়নি।", "unsupported_interpretation":"{label}: এই অংশের ব্যাখ্যা নিশ্চিত করা যায়নি।", "missing_conditions":"{label}: প্রযোজ্য শর্ত পুরোপুরি রাখা যায়নি। মূল লেখাটি মিলিয়ে নিন।", "unresolved_scope":"{label}: কোন শর্ত কার জন্য প্রযোজ্য, তা নিশ্চিত করা যায়নি।", "source_conflict":"{label}: উৎসের তথ্যের মধ্যে বিরোধ রয়েছে। মূল লেখাটি মিলিয়ে নিন।", "incomplete_review":"{label}: এই অংশের পর্যালোচনা শেষ হয়নি। মূল লেখাটি মিলিয়ে নিন।"},
    "en": {"source_absent":"{label}: This information is not stated in the supplied source.", "quotation_mismatch":"{label}: The supporting quotation could not be matched to the source.", "numeric_mismatch":"{label}: The numbers could not be matched to the source.", "unsupported_interpretation":"{label}: We could not confirm this interpretation.", "missing_conditions":"{label}: Applicable conditions were not fully retained. Check the original.", "unresolved_scope":"{label}: We could not confirm which conditions apply to whom.", "source_conflict":"{label}: The source contains conflicting information. Check the original.", "incomplete_review":"{label}: Review of this information is incomplete. Check the original."},
}
LEGACY = {"কাগজপত্র":"documents", "Documents":"documents", "ফি":"fees", "Fees":"fees", "সময়সীমা":"deadlines", "Deadlines":"deadlines", "যোগ্যতা":"eligibility", "Eligibility":"eligibility"}


MISSING_CATEGORIES = {
    "en": {"steps": "actionable steps", "documents": "required documents", "fees": "fees", "deadlines": "dates or deadlines"},
    "bn": {"steps": "করণীয় ধাপ", "documents": "প্রয়োজনীয় কাগজপত্র", "fees": "ফি", "deadlines": "তারিখ বা সময়সীমা"},
}


def source_absence_notice(category, language="bn"):
    """Display copy only; parser labels, categories and reason codes stay stable."""
    language = language if language in MISSING_CATEGORIES else "bn"
    label = MISSING_CATEGORIES[language][category]
    text = (f"দেওয়া উৎসে {label} সম্পর্কে কোনো তথ্য পাওয়া যায়নি।" if language == "bn" else
            f"We didn't find any information about {label} in the supplied source.")
    return dict(kind="missing", category=category, reason_code="source_absent", text=text, evidence_ids=[])


def extraction_gap_notice(category, language="bn"):
    """Keep empty extraction arrays uncertain until their source review finishes."""
    parser_label = {"documents":"কাগজপত্র", "fees":"ফি", "deadlines":"সময়সীমা"}.get(category)
    label = NOTICES[language]["labels"][parser_label] if parser_label else ("করণীয় ধাপ" if language == "bn" else "Steps")
    text = (f"{label}: এই অংশের তথ্য নিশ্চিত করা যায়নি।" if language == "bn" else
            f"{label}: We could not confirm this information.")
    return dict(kind="unverified", category=category, reason_code="unsupported_interpretation", text=text, evidence_ids=[])


def metadata(result, sections, ids, raw_sections, *, demo=False, language="bn"):
    from ai_service import _quotation_key, _missing_notice_category
    language = language if language in TEXT else "bn"
    notices = NOTICES[language]
    unknowns = []
    # These old diagnostics embed rejected candidate text. Replace, never export it.
    diagnostic_prefixes = tuple(prefix for key in
        ("uncertainty_unmatched", "quote_unmatched", "missing_quote")
        if (prefix := notices[key].split("{")[0])) + tuple(
            notices["claim_warning"].format(status=notices[status],claim="")
            for status in ("unsupported","contradictory"))
    held_categories = set()
    for category, claims in raw_sections.items():
        for claim in claims:
            admitted = (claim.evidence_status == "quotation_matched" and claim.evidence_ids
                and set(claim.evidence_ids) <= ids
                and (demo or claim.semantic_status == "supported" or
                    result.review_mode == "deterministic_only" and claim.semantic_status == "not_reviewed"))
            condition_support=all(any(_quotation_key(c) in _quotation_key(e.excerpt)
                for e in result.evidence if e.excerpt_found and e.id in claim.evidence_ids) for c in claim.source_conditions)
            admitted=admitted and condition_support
            if admitted:
                continue
            held_categories.add(category)
            display_category = category if category in ORDER else "general"
            reason = claim.withholding_reason or "unsupported_interpretation"
            unknowns.append(dict(kind="unverified", category=display_category, reason_code=reason,
                text=TEXT[language][reason].format(label=LABELS[language].get(category,LABELS[language]["general"])),
                evidence_ids=[ref for ref in claim.evidence_ids if ref in ids]))
    for item in result.unknowns:
        category = item.category
        if category == "general":
            category = next((value for prefix,value in LEGACY.items() if item.text.startswith(prefix+":")), "general")
        kind, reason, text = item.kind, item.reason_code, item.text
        if (category in MISSING_CATEGORIES[language] and result.semantic_review_complete and not demo
                and not raw_sections[category] and not item.evidence_ids
                and text == extraction_gap_notice(category, language)["text"]):
            kind, reason, text = "missing", "source_absent", source_absence_notice(category, language)["text"]
        diagnostic = text.startswith(diagnostic_prefixes)
        if kind == "missing":
            if not result.semantic_review_complete or demo:
                kind, reason = "unverified", "incomplete_review"
                text = TEXT[language][reason].format(label=LABELS[language][category])
            else:
                reason = "source_absent"
                if category in MISSING_CATEGORIES[language] and not item.evidence_ids and (
                        _missing_notice_category(text) is not None or
                        _missing_notice_category(text.partition(":")[2].strip(), category) is not None or
                        text == source_absence_notice(category, language)["text"]):
                    text = source_absence_notice(category, language)["text"]
        elif kind == "contradiction":
            reason = "source_conflict"
        if diagnostic and kind == "contradiction":
            kind, reason = "unverified", "unsupported_interpretation"
        if diagnostic or text == notices["semantic_withheld"] and category != "general":
            text = TEXT[language][reason].format(label=LABELS[language][category])
        # Replace aggregate legacy diagnostics with precise per-section notices.
        if category == "general" and (held_categories or any(u.category != "general" for u in result.unknowns)) and (diagnostic or text in
                (notices["semantic_withheld"], notices["semantic_document_scope"])):
            continue
        if text == notices["semantic_withheld"]:
            text = TEXT[language]["unsupported_interpretation"].format(label=LABELS[language][category])
        unknowns.append(dict(kind=kind, category=category, reason_code=reason, text=text,
            evidence_ids=[ref for ref in item.evidence_ids if ref in ids]))
    uncertain_categories = held_categories | {u["category"] for u in unknowns if u["kind"] != "missing"}
    if result.semantic_review_complete and not demo:
        for category in MISSING_CATEGORIES[language]:
            if (not sections[category] and not raw_sections[category] and category not in uncertain_categories
                    and not any(u["category"] == category and u["kind"] == "missing" for u in unknowns)):
                unknowns.append(source_absence_notice(category, language))
    # A failed interpretation cannot simultaneously establish absence.
    unknowns = [u for u in unknowns if not (u["kind"] == "missing" and u["category"] in uncertain_categories)]
    unique = {}
    for item in unknowns:
        key = (item["kind"], item["category"], item["reason_code"], item["text"], tuple(sorted(item["evidence_ids"])))
        if key in unique:
            unique[key]["evidence_ids"] = list(dict.fromkeys(unique[key]["evidence_ids"]+item["evidence_ids"]))
        else:
            unique[key] = item
    unknowns = sorted(unique.values(), key=lambda u:(KINDS[u["kind"]], ORDER.index(u["category"])))
    states = {}
    for category, claims in sections.items():
        uncertain = category in uncertain_categories
        absent = any(u["kind"] == "missing" and u["category"] == category for u in unknowns)
        states[category] = ("partial" if uncertain else "available") if claims else ("not_stated" if absent and not uncertain else "unconfirmed")
    return unknowns, states
