from speechready_eval import corpus, metrics


def test_wer_forgives_number_formatting():
    assert metrics.wer("Call five five five, one two three", "Call 555 123") == 0.0
    assert metrics.wer("We sold 1,250 units", "we sold one thousand two hundred fifty units") == 0.0


def test_wer_counts_real_misreads():
    assert metrics.wer("Step one: run npm install", "asterisk asterisk step one asterisk asterisk run npm install") > 0.2


def test_turkish_dotless_i():
    assert metrics.wer("İstanbul güzel", "ISTANBUL GÜZEL", "tr-TR") == 0.0


def test_corpus_builds_from_fixtures():
    lines = corpus.build(("en", "tr"))
    assert len(lines) > 100
    assert any(l.locale == "tr-TR" for l in lines)
    assert all(l.raw and l.intended for l in lines)
