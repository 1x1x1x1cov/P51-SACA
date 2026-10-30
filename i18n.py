"""
English / Swahili interface text for the SACA app.

Templates call _("English text"). The English text is the key; SW holds the Swahili. A missing Swahili entry falls
back to English (tests/test_app_i18n.py fails if any template string has no Swahili entry).
The Swahili is a DRAFT written without a native speaker. Have it checked before real use.
"""
from flask import g, request, session

LANGS = ("en", "sw")

SW = {}  # filled from i18n_sw.py


def get_lang():
    lang = session.get("lang")
    if lang in LANGS:
        return lang
    best = request.accept_languages.best_match(LANGS) if request else None
    return best or "en"


def gettext(text, **kwargs):
    lang = getattr(g, "lang", "en")
    out = SW.get(text, text) if lang == "sw" else text
    if kwargs:
        out = out.format(**kwargs)
    return out


def pick(pair, lang=None):
    """Choose from a {"en": ..., "sw": ...} dict (guidance and conditions use these)."""
    if not pair:
        return ""
    lang = lang or getattr(g, "lang", "en")
    return pair.get(lang) or pair.get("en") or ""


def init_app(app):
    from i18n_sw import SW as table
    SW.update(table)

    @app.before_request
    def _set_lang():
        g.lang = get_lang()

    app.jinja_env.globals.update(_=gettext, pick=pick)
