import re


def render_comment(author, text):
    strip = lambda s: re.sub(r"(?i)<(script|img)[^>]*>", "", s)
    return '<div class="comment"><b>%s</b>: %s</div>' % (strip(author), strip(text))
