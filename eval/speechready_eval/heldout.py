"""Build the held-out corpus: real LLM answers the rules were never developed against.

    python -m speechready_eval.heldout            # writes eval/corpus/heldout.en.yaml and heldout.tr.yaml
    python -m speechready_eval.heldout --dry-run  # prints the user turns

The main corpus is mostly the spec fixtures, so it measures the classes the library
targets on the inputs the rules were written against. This file is the independent
check. We wrote 30 user turns per language, the kind a voice agent hears (orders,
appointments, directions, prices, tech help, homework). An LLM answered each one as
a chat assistant would, with no instruction about speech, and its answer is the
`input`. The same model, in a separate call, wrote the narration a professional
reader would speak for that answer; that is the `intended` text the scorer compares
both the raw and the processed recording against. Nothing was edited by hand; the
answers are whatever the model returned.

Needs OPENAI_API_KEY. Re-running regenerates the files, so the committed ones are
the record of what was evaluated.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

import httpx
import yaml

OUT = Path(__file__).resolve().parents[1] / "corpus"
MODEL = "gpt-4.1-mini"

ASSISTANT_SYSTEM = {
    "en-US": "You are a helpful assistant in a chat app. Answer the user's message concisely, in two to five sentences. Format as you normally would.",
    "tr-TR": "Bir sohbet uygulamasında yardımcı bir asistansın. Kullanıcının mesajını kısa ve öz, iki ila beş cümleyle, Türkçe yanıtla. Normalde nasıl biçimlendiriyorsan öyle biçimlendir.",
}

NARRATOR_SYSTEM = {
    "en-US": (
        "You turn a chat assistant's written answer into exactly the words a professional narrator would say aloud. "
        "Rules: keep every word of the answer in the same order and do not add or paraphrase anything. "
        "Say every number, date, time, price, percentage, phone number and unit in words as a native speaker would say them. "
        "Remove markdown symbols (asterisks, hashes, backticks, pipes, dashes used as bullets) but keep the words; keep the numbers of a numbered list. "
        "For a link say only the site name (for example example.com). Say nothing for a fenced code block; keep inline code as its words. Omit emoji. "
        "Output only the narration, as plain text."
    ),
    "tr-TR": (
        "Bir sohbet asistanının yazılı yanıtını, profesyonel bir seslendirmenin sesli olarak söyleyeceği kelimelere çevirirsin. "
        "Kurallar: yanıttaki her kelimeyi aynı sırada koru; hiçbir şey ekleme ve başka sözcüklerle ifade etme. "
        "Her sayıyı, tarihi, saati, fiyatı, yüzdeyi, telefon numarasını ve birimi bir Türkün söyleyeceği gibi, eklerini ünlü uyumuna göre bitiştirerek, kelimelerle yaz. "
        "Markdown işaretlerini (yıldız, diyez, ters tırnak, dikey çizgi, madde işareti olan tireler) kaldır ama kelimeleri koru; numaralı listenin numaralarını koru. "
        "Bir bağlantı için yalnızca site adını söyle (örneğin example.com). Çitli kod bloğu için hiçbir şey söyleme; satır içi kodu kelimeleri olarak koru. Emojileri atla. "
        "Yalnızca seslendirme metnini düz metin olarak yaz."
    ),
}

# The user turns. Written by us; the answers and narrations are the model's.
TURNS = {
    "en-US": [
        ("support", "My order hasn't arrived yet, it's been 10 days. What can I do?"),
        ("support", "How do I reset my password if I no longer have access to my old email?"),
        ("support", "Can you summarize your refund policy for a subscription I cancelled yesterday?"),
        ("banking", "What's the difference between APR and APY on a savings account?"),
        ("banking", "I was charged $39.99 twice for the same thing. How do I dispute it?"),
        ("banking", "How long does an international wire transfer usually take and what does it cost?"),
        ("scheduling", "Can you suggest a time for a 45-minute call next week with someone in Tokyo if I'm in New York?"),
        ("scheduling", "Remind me what I need to prepare for a dentist appointment on March 3rd at 9:30."),
        ("scheduling", "I need to move my 2pm Thursday meeting to Friday morning. Draft a short message to the attendees."),
        ("travel", "How do I get from JFK to Manhattan by public transport, and roughly how much does it cost?"),
        ("travel", "What should I know about tipping in Turkey as a tourist?"),
        ("travel", "My flight is delayed 3 hours. What am I entitled to under EU rules?"),
        ("tech", "My Python script says ModuleNotFoundError for requests. How do I fix it?"),
        ("tech", "Give me a quick way to find which process is using port 8080 on macOS."),
        ("tech", "What's the simplest way to schedule a backup script to run every night at 2am on Linux?"),
        ("education", "Explain photosynthesis to a 12-year-old in a few sentences."),
        ("education", "What's the Pythagorean theorem and give me one worked example."),
        ("education", "How do I convert 72 degrees Fahrenheit to Celsius, step by step?"),
        ("health", "How much water should an adult drink per day, roughly?"),
        ("health", "What's a normal resting heart rate and when should I worry?"),
        ("health", "How often should I replace my toothbrush and why?"),
        ("shopping", "Which is the better deal: 3 for $10 or 25% off $4.50 each?"),
        ("shopping", "I'm looking for a laptop for video editing under $1,500. What specs matter most?"),
        ("shopping", "When does your Black Friday sale start and how long does shipping take?"),
        ("billing", "My electricity bill went from $80 to $140 this month. What could explain that?"),
        ("billing", "How do I read the usage section of my internet bill?"),
        ("billing", "Can you explain what a prorated charge is with a quick example?"),
        ("local", "What's the weather usually like in Ankara in November?"),
        ("local", "What time do most pharmacies close on Sundays and how do I find an open one?"),
        ("local", "Give me a two-sentence overview of what to see in Istanbul in one day."),
    ],
    "tr-TR": [
        ("support", "Siparişim 10 gündür gelmedi, ne yapabilirim?"),
        ("support", "Eski e-postama erişimim yok, şifremi nasıl sıfırlarım?"),
        ("support", "Dün iptal ettiğim abonelik için iade koşullarını özetler misin?"),
        ("banking", "Vadeli hesapta brüt faizle net faiz arasındaki fark ne?"),
        ("banking", "Kartımdan aynı şey için iki kez 399,90 TL çekildi. Nasıl itiraz ederim?"),
        ("banking", "Yurt dışına havale ne kadar sürer ve ücreti ne kadar olur?"),
        ("scheduling", "Gelecek hafta Berlin'deki bir müşteriyle 45 dakikalık bir görüşme için uygun bir saat öner, ben Ankara'dayım."),
        ("scheduling", "3 Mart saat 9.30'daki diş hekimi randevum için ne hazırlamalıyım, hatırlat."),
        ("scheduling", "Perşembe 14.00'teki toplantıyı cuma sabahına almam lazım. Katılımcılara kısa bir mesaj yaz."),
        ("travel", "İstanbul Havalimanı'ndan Taksim'e toplu taşımayla nasıl giderim, yaklaşık ne kadar tutar?"),
        ("travel", "Almanya'ya ilk kez gidiyorum, bahşiş konusunda ne bilmeliyim?"),
        ("travel", "Uçağım 3 saat rötarlı. Yolcu haklarıma göre neye hakkım var?"),
        ("tech", "Python betiğim requests için ModuleNotFoundError veriyor. Nasıl düzeltirim?"),
        ("tech", "macOS'ta 8080 portunu hangi işlemin kullandığını nasıl bulurum?"),
        ("tech", "Linux'ta bir yedekleme betiğini her gece 02.00'de çalıştırmanın en basit yolu ne?"),
        ("education", "Fotosentezi 12 yaşındaki bir çocuğa birkaç cümleyle anlat."),
        ("education", "Pisagor teoremi nedir, bir çözümlü örnek ver."),
        ("education", "72 Fahrenheit kaç santigrat derece, adım adım göster."),
        ("health", "Bir yetişkin günde yaklaşık ne kadar su içmeli?"),
        ("health", "Normal dinlenme nabzı kaçtır, ne zaman endişelenmeliyim?"),
        ("health", "Diş fırçamı ne sıklıkla değiştirmeliyim, neden?"),
        ("shopping", "Hangisi daha hesaplı: 3 tanesi 100 TL mi, yoksa tanesi 45 TL'ye yüzde 25 indirim mi?"),
        ("shopping", "Video düzenleme için 60.000 TL altı bir dizüstü arıyorum. En çok hangi özellikler önemli?"),
        ("shopping", "Kasım indirimleri ne zaman başlıyor ve kargo kaç günde gelir?"),
        ("billing", "Elektrik faturam bu ay 800 TL'den 1.400 TL'ye çıktı. Sebebi ne olabilir?"),
        ("billing", "İnternet faturamdaki kullanım bölümünü nasıl okurum?"),
        ("billing", "Kıst ücret nedir, kısa bir örnekle açıklar mısın?"),
        ("local", "Ankara'da kasım ayında hava genelde nasıl olur?"),
        ("local", "Nöbetçi eczaneyi nasıl bulurum, eczaneler pazar günü kaçta kapanır?"),
        ("local", "Bir günde İstanbul'da görülecek yerleri iki cümleyle özetle."),
    ],
}


def _chat(system: str, user: str, temperature: float) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set")
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL, "temperature": temperature,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def build(locale: str) -> list[dict]:
    cases = []
    counts: dict[str, int] = {}
    for domain, question in TURNS[locale]:
        counts[domain] = counts.get(domain, 0) + 1
        answer = _chat(ASSISTANT_SYSTEM[locale], question, temperature=0.7)
        narration = _chat(NARRATOR_SYSTEM[locale], answer, temperature=0.0)
        cases.append({"id": f"{domain}-{counts[domain]}", "cls": f"heldout/{domain}", "question": question,
                      "input": answer, "intended": narration})
        print(f"{locale} {domain}-{counts[domain]}: {len(answer)} chars", file=sys.stderr)
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--locales", default="en-US,tr-TR")
    args = ap.parse_args(argv)
    for locale in args.locales.split(","):
        if args.dry_run:
            for d, q in TURNS[locale]:
                print(f"{locale} [{d}] {q}")
            continue
        cases = build(locale)
        lang = locale.split("-")[0]
        header = (
            f"# Held-out corpus: {len(cases)} answers from {MODEL} to user turns written for a voice agent,\n"
            f"# generated {dt.date.today().isoformat()} by speechready_eval.heldout, unedited. `input` is the model's\n"
            f"# answer as a chat assistant; `intended` is the narration the same model wrote for it in a\n"
            f"# separate call (numbers in words, no markdown, links by domain, code blocks skipped).\n"
        )
        body = yaml.safe_dump({"locale": locale, "cases": cases}, allow_unicode=True, sort_keys=False, width=1000)
        (OUT / f"heldout.{lang}.yaml").write_text(header + body, encoding="utf-8")
        print(f"{len(cases)} cases -> {OUT / f'heldout.{lang}.yaml'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
