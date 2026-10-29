"""Synthetic source fixtures, not real government instructions."""

import json

from google.genai import types

SOURCE = "অনলাইনে আবেদন করুন। আবেদনের সঙ্গে জন্মনিবন্ধনের অনুলিপি দিন।"


def claim(text="অনলাইনে আবেদন করতে হবে।", refs=None, status="source_stated"):
    return {"text": text, "evidence_ids": ["e1"] if refs is None else refs, "status": status}


def payload():
    return {
        "explanation": [claim()],
        "steps": [claim()],
        "documents": [claim("জন্মনিবন্ধনের অনুলিপি দিন।", ["e2"])],
        "fees_and_deadlines": {"fees": [], "deadlines": []},
        "unknowns": [],
        "evidence": [
            {"id": "e1", "excerpt": "অনলাইনে আবেদন করুন।"},
            {"id": "e2", "excerpt": "আবেদনের সঙ্গে জন্মনিবন্ধনের অনুলিপি দিন।"},
        ],
    }


def misplaced_missing_notices():
    """Reproduce the successful live call's misplaced notices without any API."""
    data = payload()
    data["fees_and_deadlines"] = {
        "fees": [claim("এই তথ্যটি দেওয়া উৎসে নেই।", [], "unsupported")],
        "deadlines": [claim("এই তথ্যটি দেওয়া উৎসে নেই।", [], "unsupported")],
    }
    data["unknowns"] = [
        {"kind": "missing", "text": "আবেদনের ফি সংক্রান্ত কোনো তথ্য দেওয়া নেই।", "evidence_ids": []},
        {"kind": "missing", "text": "আবেদনের সময়সীমা সংক্রান্ত কোনো তথ্য দেওয়া নেই।", "evidence_ids": []},
    ]
    return data


def wire_payload(data):
    """Translate historical flat fixtures into the new provider wire contract.

    Archived fixture files and their semantic expectations remain unchanged.
    Invalid legacy structures are returned unchanged to exercise parser rejection.
    """
    import copy, re
    if not isinstance(data,dict) or "evidence" not in data:
        return data
    try:
        evidence = data["evidence"]
        ids = [e["id"] for e in evidence]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"e[1-9][0-9]{0,5}",i) for i in ids):
            return data
        quotes = {e["id"]:e["excerpt"] for e in evidence}
        def convert(item, unknown=False):
            refs = item["evidence_ids"]
            if not isinstance(refs,list) or any(not isinstance(i,str) or not re.fullmatch(r"e[1-9][0-9]{0,5}",i) for i in refs):
                raise ValueError()
            result = {"source_quotes":[quotes.get(ref,"UNMATCHED FIXTURE REFERENCE "+ref) for ref in refs],"source_conditions":copy.deepcopy(item.get("source_conditions",[]))}
            result.update({k:copy.deepcopy(v) for k,v in item.items() if k!="evidence_ids"})
            if unknown:
                result.pop("source_conditions",None)
                result.setdefault("category","general")
                result.setdefault("reason_code","source_absent" if item["kind"]=="missing" else "source_conflict" if item["kind"]=="contradiction" else "unsupported_interpretation")
            return result
        result = {k:copy.deepcopy(v) for k,v in data.items() if k!="evidence"}
        for section in ("explanation","steps","documents"):
            result[section] = [convert(item) for item in data[section]]
        result["fees_and_deadlines"] = {k:[convert(item) for item in data["fees_and_deadlines"][k]] for k in ("fees","deadlines")}
        result["unknowns"] = [convert(item,True) for item in data["unknowns"]]
        return result
    except (KeyError,TypeError,ValueError):
        return data


def response(data=None, *, text=None, finish_reason=types.FinishReason.STOP):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(parts=[types.Part(text=text if text is not None else json.dumps(wire_payload(data if data is not None else payload()), ensure_ascii=False))]),
        finish_reason=finish_reason,
    )])


def prepare_text(app, text=SOURCE):
    """Apply a pasted source through the actual secondary input, without analysis."""
    app.text_area(key="paste_text").input(text).run()
    app.button(key="use_text").click().run()
    return app
