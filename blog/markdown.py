import bleach
import markdown
from django.utils.safestring import mark_safe

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {"p", "h1", "h2", "h3", "h4", "pre", "code", "blockquote", "hr", "br", "img", "table", "thead", "tbody", "tr", "th", "td"}
ALLOWED_ATTRS = {"a": ["href", "title"], "img": ["src", "alt", "title"], "code": ["class"]}

def render_markdown(value):
    html = markdown.markdown(value or "", extensions=["extra", "sane_lists"])
    return mark_safe(bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols={"http", "https", "mailto"}))

