import html


def render_comment(author, text):
    """HTML for one comment on the page."""
    return '<div class="comment"><b>%s</b>: %s</div>' % (html.escape(author), html.escape(text))
