"""The offline lexicon builder, with the model call replaced by a canned answer."""

import json
from pathlib import Path

import pytest

from speechready import Lexicon, builder, prepare
from speechready.cli import main

TEXT = "Restart Nginx, check the API logs on GitHub and the S3 bucket. Node.js and C++ too. API'yi çağır. The API is fine."


def test_scan_finds_acronyms_mixed_case_and_inner_punctuation():
    found = dict(builder.scan(TEXT))
    assert found["API"] == 3 and found["GitHub"] == 1 and found["S3"] == 1 and found["Node.js"] == 1 and found["C++"] == 1
    assert "Nginx" not in found and "The" not in found and "bucket" not in found
    assert builder.scan(TEXT, min_count=2) == [("API", 3)]


def test_read_glossary_takes_hints_and_comments():
    words = builder.read_glossary("# tech\nNginx\tweb server\nkubectl  the Kubernetes CLI\n\nSQL # database\nnginx\n")
    assert words == [("Nginx", "web server"), ("kubectl", "the Kubernetes CLI"), ("SQL", "")]


def fake_ask(answers):
    calls = []

    def ask(system, user):
        calls.append((system, user))
        words = [w["word"] for w in json.loads(user)]
        entries = [{"word": w, **answers[w]} for w in words]
        return "```json\n" + json.dumps({"entries": entries}) + "\n```", {"prompt_tokens": 10, "completion_tokens": 5}

    ask.calls = calls
    return ask


ANSWERS = {
    "Nginx": {"say": "engine x", "keep": False, "note": ""},
    "SQL": {"say": "sequel", "keep": False, "note": "some say es kyu el"},
    "Berlin": {"say": "", "keep": True, "note": ""},
    "IT": {"say": "ay ti", "keep": False, "case_sensitive": True, "note": ""},
}


def test_build_adds_entries_and_reports_the_rest():
    ask = fake_ask(ANSWERS)
    result = builder.build([("Nginx", "web server"), ("SQL", ""), ("Berlin", ""), ("IT", "")], "tr-TR", ask=ask)
    assert [e.word for e in result.added] == ["Nginx", "SQL", "IT"]
    assert result.kept == [("Berlin", "")] and result.notes == [("SQL", "some say es kyu el")]
    assert result.added[2].case_sensitive and not result.added[0].case_sensitive
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5}
    system, user = ask.calls[0]
    assert "Turkish" in system and '"ipa"' not in system
    assert json.loads(user)[0] == {"word": "Nginx", "hint": "web server"}
    assert prepare("Nginx'i IT ile kur.", locale="tr-TR", lexicon=result.lexicon).text == "engine x'i ay ti ile kur."
    assert prepare("it", locale="tr-TR", lexicon=result.lexicon).text == "it."


def test_build_skips_words_already_in_the_lexicon_and_batches():
    have = Lexicon.from_entries([{"word": "sql", "say": "sequel"}], "en-US")
    ask = fake_ask(ANSWERS)
    result = builder.build([("SQL", ""), ("Nginx", ""), ("IT", "")], "en-US", lexicon=have, ask=ask, batch=1)
    assert result.skipped == ["SQL"] and [e.word for e in result.added] == ["Nginx", "IT"] and len(ask.calls) == 2
    assert [e.word for e in result.lexicon.entries] == ["sql", "Nginx", "IT"]
    assert ask.calls[0][0].endswith("follow their conventions:\nsql -> sequel")
    assert ask.calls[1][0] == ask.calls[0][0]


def test_build_asks_for_ipa_when_wanted():
    ask = fake_ask({"Nginx": {"say": "engine x", "ipa": "ˈɛndʒɪnˈɛks"}})
    result = builder.build([("Nginx", "")], "en-US", ask=ask, ipa=True)
    assert '"ipa"' in ask.calls[0][0] and result.added[0].ipa == "ˈɛndʒɪnˈɛks"
    result = builder.build([("Nginx", "")], "en-US", ask=fake_ask({"Nginx": {"say": "engine x", "ipa": "x"}}))
    assert result.added[0].ipa == ""


def test_build_rejects_an_answer_that_drops_a_word():
    with pytest.raises(ValueError, match="no entry for 'SQL'"):
        builder.build([("SQL", "")], "en-US", ask=lambda s, u: ('{"entries": []}', {}))


def test_check_flags_symbols_and_unmatched_words():
    lex = Lexicon.from_entries([{"word": "Nginx", "say": "engine x"}, {"word": "S3", "say": "s 3"},
                                {"word": "CLI", "spell": True}, {"word": "nothing"}], "en-US")
    problems = dict(builder.check(lex))
    assert "Nginx" not in problems and "CLI" not in problems
    assert "digits or symbols" in problems["S3"] and "no say" in problems["nothing"]
    tr = Lexicon.from_entries([{"word": "WiFi", "say": "wayfay"}, {"word": "API", "say": "ey pi ay"}], "tr-TR")
    assert [w for w, _ in builder.check(tr)] == ["WiFi"] and "Turkish alphabet lacks" in builder.check(tr)[0][1]


def test_yaml_round_trip_keeps_every_field(tmp_path: Path):
    lex = Lexicon.from_entries([{"word": "IT", "say": "ay ti", "case_sensitive": True}, {"word": "CLI", "spell": True},
                                {"word": "Nginx", "ipa": "ˈɛndʒɪnˈɛks", "say": "engine x"}, {"word": 'a"b', "say": "ey bi"}], "tr-TR")
    path = tmp_path / "lex.yaml"
    builder.write(lex, path, ["first line", "", "third"])
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# first line\n#\n# third\nlocale: tr-TR\nentries:\n")
    assert Lexicon.load(path).to_dict() == lex.to_dict() and builder.header_of(path) == ["first line", "", "third"]


def test_cli_build_extends_an_existing_file(tmp_path: Path, monkeypatch, capsys):
    glossary = tmp_path / "glossary.txt"
    glossary.write_text("Nginx\tweb server\nSQL\nBerlin\n", encoding="utf-8")
    out = tmp_path / "lexicon.yaml"
    monkeypatch.setattr(builder, "chat", lambda s, u, **kw: fake_ask(ANSWERS)(s, u))

    assert main(["lexicon", "build", str(glossary), "-o", str(out), "--locale", "en-US", "--dry-run"]) == 0
    assert not out.exists() and capsys.readouterr().out.split() == ["Nginx", "SQL", "Berlin"]

    assert main(["lexicon", "build", str(glossary), "-o", str(out), "--locale", "en-US"]) == 0
    err = capsys.readouterr().err
    assert "2 entries added, 1 words the model says the voice reads as written" in err and "kept as written: Berlin" in err
    first = out.read_text(encoding="utf-8")
    assert first.startswith("# Pronunciation lexicon drafted by `speechready lexicon build` on ") and "gpt-4.1-mini" in first
    assert [e.word for e in Lexicon.load(out).entries] == ["Nginx", "SQL"]

    glossary.write_text("Nginx\nSQL\nIT\n", encoding="utf-8")
    assert main(["lexicon", "build", str(glossary), "-o", str(out), "--locale", "en-US"]) == 0
    assert "1 entries added" in capsys.readouterr().err
    second = out.read_text(encoding="utf-8")
    assert second.startswith(first.split("locale:")[0]) and [e.word for e in Lexicon.load(out).entries] == ["Nginx", "SQL", "IT"]

    assert main(["lexicon", "build", str(glossary), "-o", str(out), "--locale", "tr-TR"]) == 2
    assert main(["lexicon", "check", str(out)]) == 0
    assert main(["lexicon", "export", str(out), "--profile", "elevenlabs-v2"]) == 0
    assert "<alias>engine x</alias>" in capsys.readouterr().out
    assert main(["lexicon", "export", str(out), "--profile", "openai-tts"]) == 1


def test_cli_scan(tmp_path: Path, capsys):
    f = tmp_path / "t.txt"
    f.write_text(TEXT, encoding="utf-8")
    assert main(["lexicon", "scan", str(f), "--min-count", "2", "--counts"]) == 0
    assert capsys.readouterr().out == "API\t# 3\n"
