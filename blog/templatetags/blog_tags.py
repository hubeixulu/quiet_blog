from django import template
from blog.markdown import render_markdown

register = template.Library()
register.filter("markdown", render_markdown)

