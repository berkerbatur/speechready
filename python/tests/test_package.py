from pathlib import Path

import speechready

SPEC = Path(__file__).resolve().parents[2] / "spec"


def test_version_is_set():
    assert speechready.__version__


def test_shared_spec_is_reachable():
    fixtures = list((SPEC / "fixtures").rglob("*.yaml"))
    assert fixtures, "the shared fixture corpus in spec/fixtures is missing"


def test_bundled_turkish_tech_lexicon():
    from speechready import list_lexicons, load_lexicon, prepare

    assert "tr-tech" in list_lexicons()
    lex = load_lexicon("tr-tech")
    assert lex.locale == "tr-TR" and len(lex.entries) > 50
    assert prepare("API'yi çağır.", locale="tr-TR", lexicon="tr-tech").text == "ey pi ay'ı çağır."
    assert prepare("API'yi çağır.", locale="tr-TR", lexicon=lex).text == "ey pi ay'ı çağır."
