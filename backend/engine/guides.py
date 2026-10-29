"""Small reviewed-source catalogue; deterministic matching, no web search or AI."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from datetime import date
from url_input import normalize_url, ExtractionError

@dataclass(frozen=True)
class Guide:
    id: str
    title_bn: str
    title_en: str
    url: str
    text: str
    scope_bn: str
    scope_en: str
    reviewed_on: str
    review_basis: str
    topics: list[str]
    intents: list[str]

    def __post_init__(self):
        if not all(isinstance(value, str) and value.strip() for value in (self.id, self.title_bn, self.title_en, self.url, self.text, self.scope_bn, self.scope_en, self.reviewed_on, self.review_basis)):
            raise ValueError("Incomplete source record")
        if len(self.text) > 10_000 or not all(isinstance(terms, list) and terms and all(isinstance(term, str) and term.strip() for term in terms) for terms in (self.topics, self.intents)):
            raise ValueError("Invalid source record")
        normalize_url(self.url)
        date.fromisoformat(self.reviewed_on)

    def title(self, language):
        return self.title_bn if language == "bn" else self.title_en

    def scope(self, language):
        return self.scope_bn if language == "bn" else self.scope_en


def load_guides(path=Path(__file__).parent / "sources/guides.json") -> list[Guide]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Guide(**item) for item in data]
    except (OSError, UnicodeError, ValueError, TypeError, ExtractionError):
        return []


def _matches_term(term: str, question: str) -> bool:
    # English catalogue terms are words, not substrings such as form/information.
    # Keep Bengali suffixes and mixed-script spelling working as before.
    term = term.casefold()
    if term.isascii():
        return bool(re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", question))
    return term in question


def matching_guides(question: str) -> list[Guide]:
    """A topic AND a supported intent must match; never answer from memory.

    New reviewed records extend this catalogue. Unrestricted discovery is deferred.
    Mixed services remain separate choices rather than one merged source.
    """
    question = re.sub(r"\s+", " ", question.casefold()).strip()
    return [guide for guide in load_guides()
            if any(_matches_term(term, question) for term in guide.topics)
            and any(_matches_term(term, question) for term in guide.intents)]
