"""Provider grammar projection; strict Pydantic validation remains local."""

_GRAMMAR_BOUNDS = frozenset({"minItems", "maxItems", "minLength", "maxLength", "default", "title"})


def strip_grammar_bounds(schema):
    """Return a new schema without expensive decoder bounds or annotations."""
    if isinstance(schema, dict):
        result = {}
        for key, value in schema.items():
            if key in _GRAMMAR_BOUNDS:
                continue
            # These dictionaries contain field/type NAMES, not schema keywords.
            # ResearchPlan has a real field named "title" that must survive.
            if key in {"properties", "$defs", "definitions", "patternProperties", "dependentSchemas"} and isinstance(value, dict):
                result[key] = {name: strip_grammar_bounds(item) for name, item in value.items()}
            else:
                result[key] = strip_grammar_bounds(value)
        return result
    if isinstance(schema, list):
        return [strip_grammar_bounds(value) for value in schema]
    return schema
