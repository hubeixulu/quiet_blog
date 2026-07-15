import bleach
import markdown
import re
from django.utils.safestring import mark_safe

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {"p", "h1", "h2", "h3", "h4", "pre", "code", "blockquote", "hr", "br", "img", "table", "thead", "tbody", "tr", "th", "td"}
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    # Toast UI stores task state on the list item instead of using an input.
    "li": ["class", "data-task", "data-task-checked"],
}

HTML_BLOCK = re.compile(r"^\s*<(?:div|p|h[1-6]|ul|ol|blockquote|pre|table|hr)(?:\s|>|/)", re.IGNORECASE)


def _prepare_legacy_text(value):
    """Make plain-text editor input behave like WYSIWYG paragraphs."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in normalized.split("\n"):
        leading_spaces = len(line) - len(line.lstrip(" "))
        if leading_spaces:
            line = "&nbsp;" * leading_spaces + line[leading_spaces:]
        lines.append(line)
    # In a visual editor Enter means a new paragraph. Markdown normally treats
    # a single newline as a soft wrap, which caused the whole article to render
    # as one paragraph.
    return "\n\n".join(lines)

def render_markdown(value):
    value = value or ""
    is_editor_html = bool(HTML_BLOCK.match(value))
    if is_editor_html:
        # Toast UI's WYSIWYG mode is stored as HTML. Passing that HTML through
        # Python-Markdown escapes wrappers such as <div><hr></div> and changes
        # the editor's document structure.
        html = value
    else:
        value = _prepare_legacy_text(value)
        # nl2br keeps the line breaks from older Markdown posts.
        html = markdown.markdown(value, extensions=["extra", "sane_lists", "nl2br"])
    return mark_safe(bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols={"http", "https", "mailto"},
        strip=True,
    ))
