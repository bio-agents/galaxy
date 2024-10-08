from markupsafe import escape as raw_escape
from galaxy.util import smart_str

ALLOWED_ELEMENTS = ["<b>", "</b>", "<br/>"]
ALLOWED_MAP = dict(map(lambda x: (x, raw_escape(x)), ALLOWED_ELEMENTS))


def escape( string ):
    """ A agent shed variant of markupsafe.escape that allows a select few
    HTML elements that are repeatedly used in messages created deep
    in the agentshed components. Ideally abstract things would be produced
    in these components and messages in the views or client side - this is
    what should be worked toward - but for now - we have this hack.

    >>> escape("A <b>repo</b>")
    u'A <b>repo</b>'
    """
    escaped = smart_str( raw_escape( string ), encoding="ascii", errors="replace" )
    # Unescape few selected tags.
    for key, value in ALLOWED_MAP.iteritems():
        escaped = escaped.replace(value, key)
    return escaped
