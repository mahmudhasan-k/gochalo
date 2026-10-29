"""Six-category projection over the legacy arrays; no duplicated saved payload."""
from pydantic import BaseModel, ConfigDict

ORDER = ("overview", "actionable_steps", "deadlines", "fees", "required_documents", "others")
LEGACY = dict(zip(ORDER, ("explanation", "steps", "deadlines", "fees", "documents", "unknowns")))


class PublicClaim(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    text: str
    evidence_ids: list[str]


def finalize(output):
    """Validate after source admission; an available category is not verification."""
    import ai_service as ai
    references = {e["id"]: e["excerpt"] for e in output["evidence"]}
    for items in output["sections"].values():
        for item in items:
            PublicClaim.model_validate(item)
            if any(ref not in references for ref in item["evidence_ids"]):
                raise ai.AnalysisError("malformed_response", "Dangling source reference.")
            if output["review_mode"] == "general_ask":
                if item["evidence_ids"]:
                    raise ai.AnalysisError("malformed_response", "General guidance cannot claim source evidence.")
                item["support_status"] = "unreviewed"
    unknowns, seen = [], {}
    for item in output["unknowns"]:
        scope = tuple(sorted({ai._quotation_key(references[ref]) for ref in item["evidence_ids"] if ref in references}))
        # One cited paragraph can contain multiple conflicts. Keep wording AND
        # passage identity; do not guess that different scoped issues are synonyms.
        wording = ai._quotation_key(item["text"])
        identity = (item["kind"], item.get("category", "general"), item.get("reason_code"), scope, wording)
        if identity in seen:
            prior = seen[identity]
            prior["evidence_ids"] = list(dict.fromkeys(prior["evidence_ids"] + item["evidence_ids"]))
        else:
            seen[identity] = item
            unknowns.append(item)
    output["unknowns"] = unknowns
    states = {}
    for category, legacy in LEGACY.items():
        if category == "others":
            states[category] = "available" if unknowns else "not_stated"
            continue
        items = output["sections"][legacy]
        topic = "general" if legacy == "explanation" else legacy
        issues = [u for u in unknowns if u.get("category", "general") == topic]
        state = "partial" if items and issues else "available" if items else (
            "not_stated" if issues and all(u.get("reason_code") == "source_absent" for u in issues) else "unconfirmed")
        states[category] = state
        output["section_states"][legacy] = state
    output.update(category_order=list(ORDER), category_states=states)
    output["has_guidance"] = bool(any(output["sections"].values()))
    return output
