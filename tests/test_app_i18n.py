"""Every interface string used with _() in the templates and views has a Swahili entry."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from i18n_sw import SW  # noqa: E402

PATTERN = re.compile(r"""_\(\s*(['"])((?:\\.|(?!\1).)*)\1""")


def _strings():
    files = list((ROOT / "templates").glob("*.html")) + [ROOT / "saca_auth.py", ROOT / "saca_views.py"]
    found = set()
    for f in files:
        for m in PATTERN.finditer(f.read_text(encoding="utf-8")):
            found.add(m.group(2).replace("\\'", "'"))
    return found


def test_all_interface_strings_have_swahili():
    missing = sorted(s for s in _strings() if s not in SW)
    assert not missing, missing


def test_placeholders_survive_translation():
    for en, sw in SW.items():
        assert set(re.findall(r"\{\w+\}", en)) == set(re.findall(r"\{\w+\}", sw)), en


def test_store_messages_have_swahili():
    import saca_store as store
    msgs = [store.validate_password("short"), store.validate_pin("12"), store.validate_pin("1111"),
            store.validate_pin("2580", "2581")]
    for m in msgs:
        assert m in SW, m
    _, errors = store.validate_patient({})
    for m in errors.values():
        assert m in SW, m
