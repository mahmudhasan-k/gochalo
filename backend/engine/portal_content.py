"""Conservative text projection of National Portal HTML, without executing it.

Select only a recognized content widget when present; otherwise keep body text.
No sentence rewriting, keyword scoring, list renumbering or body deduplication.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import re


class PortalText(HTMLParser):
    VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "base", "embed", "param", "col"}
    BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "caption", "blockquote", "pre"}
    # Header/footer/form elements can contain dates, submission instructions or
    # footnotes. Drop executable/navigation furniture, not semantic containers.
    SKIP = {"nav", "script", "style", "noscript", "button", "svg", "head"}
    CHROME = {"print-widget", "chips", "image-list", "share-widget", "social-share", "accessibility-card"}

    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.stack = []
        self.all_text = []
        self.content = []
        self.found = False

    def emit(self, value):
        if self.stack and self.stack[-1][1]:
            return
        self.all_text.append(value)
        if self.stack and self.stack[-1][2]:
            self.content.append(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        parent_skip = bool(self.stack and self.stack[-1][1])
        root = "content-viewer-widget" in classes or attrs.get("data-widget_name") == "ContentViewerWidget"
        self.found |= root
        active = root or bool(self.stack and self.stack[-1][2])
        skip = parent_skip or tag in self.SKIP or bool(classes & self.CHROME)
        href = urljoin(self.url, attrs.get("href", "")) if tag == "a" and attrs.get("href") else ""
        if href and urlsplit(href).scheme not in {"http", "https"}:
            href = ""
        self.stack.append((tag, skip, active, href))
        if href:
            self.emit("[")
        if tag in self.BLOCK or tag in {"br", "hr"}:
            self.emit("\n")
        if tag in {"td", "th"}:
            self.emit(" | ")
        if tag == "img" and attrs.get("alt"):
            self.emit("![" + attrs["alt"] + "](" + attrs.get("src", "") + ")")
        if tag in self.VOID:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), None)
        if index is None:
            return
        if tag == "a" and self.stack[index][3]:
            self.emit("](" + self.stack[index][3] + ")")
        if tag in self.BLOCK:
            self.emit("\n")
        del self.stack[index:]

    def handle_data(self, data):
        self.emit(data)


def portal_text(html, url):
    parser = PortalText(url)
    parser.feed(html)
    parser.close()
    text = "".join(parser.content if parser.found else parser.all_text)
    # HTML indentation is layout, while paragraph/table/list boundaries stay.
    text = "\n".join(re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()
