#!/usr/bin/env python3
"""Deterministic, scalable benchmark corpora for SoMaJo.

Each corpus is a list of paragraph strings, generated reproducibly from a
seed so that benchmark and differential runs are comparable across commits.
The categories deliberately stress different clusters of the tokenizer:

    de_cmc    German computer-mediated communication: emoticons, abbreviations,
              mentions, hashtags, URLs, dates, numbers — the home turf.
    en_web    English web text: contractions, possessives, hyphenation.
    de_prose  Long, "boring" German prose: low special-character density. This
              exercises the common path (whitespace/dot/word rules), where most
              real-world runtime is actually spent.
    emoji     Emoji-heavy social media: stresses the #1 hotspot (grapheme pass).
    mixed     A representative blend of the above.

`xml_sample()` returns a single HTML-ish XML string for the XML pipeline.

Generation mixes a bank of hand-written, linguistically varied templates with
light parametric variation (names, numbers, dates) so the corpus is neither a
single repeated string (which would over-reward caches) nor random noise.
"""

import hashlib
import json
import os
import random
from xml.sax.saxutils import escape as _xml_escape

__all__ = ["CATEGORIES", "make_corpus", "corpus_stats", "xml_sample", "LANG_OF",
           "empirist_available", "load_empirist"]

# Real EmpiriST 2015 gold-standard text (CC-BY-SA), extracted from the corpus
# VRT (space-joined gold tokens). Optional: present only if the file was built
# from a local checkout of github.com/fau-klue/empirist-corpus. Gives the
# benchmark and differential real German CMC/web vocabulary, not just synthetic.
_EMPIRIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "empirist_real_text.json")


def empirist_available():
    return os.path.exists(_EMPIRIST_PATH)


def load_empirist(subcorpus, n=None, seed=0):
    """Real EmpiriST text for ``subcorpus`` in {'cmc', 'web'}. With ``n``,
    deterministically sample (with replacement) to n paragraphs for
    benchmarking; without, return all paragraphs (for the differential)."""
    with open(_EMPIRIST_PATH, encoding="utf-8") as fh:
        paras = json.load(fh)[subcorpus]
    if n is None:
        return paras
    rng = random.Random(seed)
    return [rng.choice(paras) for _ in range(n)]

CATEGORIES = ["de_cmc", "en_web", "de_prose", "emoji", "mixed"]

# Recommended language per category for the SoMaJo constructor.
LANG_OF = {
    "de_cmc": "de_CMC",
    "en_web": "en_PTB",
    "de_prose": "de_CMC",
    "emoji": "de_CMC",
    "mixed": "de_CMC",
}

_NAMES = ["maxmustermann", "lisa_k", "der_echte_tom", "anna2000", "berlin_news",
          "FCBayern", "tagesschau", "heise_online", "j.doe", "MariaH"]
_HASHTAGS = ["sommer", "urlaub", "wahl2021", "klimawandel", "fussball", "fail",
             "ootd", "foodporn", "montagsmotivation", "berlin"]
_DOMAINS = ["example.com", "tagesschau.de", "heise.de", "github.com", "spiegel.de",
            "uni-erlangen.de", "wikipedia.org"]
_EMOJI = ["\U0001f600", "\U0001f602", "\U0001f60d", "\U0001f44d", "\U0001f525",
          "❤️", "\U0001f389", "\U0001f937‍♂️",
          "\U0001f1e9\U0001f1ea", "\U0001f468‍\U0001f469‍\U0001f467",
          "☀️", "⭐", "✅", "\U0001f44f\U0001f3fb"]

# --- German CMC templates (use {p} placeholders filled by _fill) ---------------
_DE_CMC = [
    "Heyi:) Was machst du morgen Abend?! Lust auf Film?;-) Ich hab um {time} Uhr Zeit.",
    "Der Preis betrug {money} Euro am {date} laut https://www.{dom}/produkt?id={n} (Quelle).",
    "Mega Wetter heute {em}{em} #{tag} #{tag} @{name} hat {n}/{n2} der Strecke geschafft.",
    "Laut §{n} Abs. {n2} BGB i.V.m. Art. 5 GG gilt das z.B. nicht für die GmbH & Co. KG.",
    "Treffen wir uns am {date} um ca. {n2} Uhr? Bring bitte {money} kg Mehl mit!!!",
    "Die Studie (Müller et al. 2019, S. 23–45) zeigt, dass viele WhatsApp tgl. nutzen.",
    "ISBN 978-3-16-148410-0 kostet {money}€ — ein Schnäppchen, oder?? doi:10.1000/xyz{n}",
    "@{name} schau mal hier: {dom}/news — voll der Hammer {em} #{tag}",
    "Bestellung Nr. {n} ist unterwegs, Lieferung am {date} zwischen {n2} und 18 Uhr.",
    "RT @{name}: Das neue Update v{n2}.0 ist da \U0001f680 mehr unter http://{dom}/blog",
]
# --- English web templates -----------------------------------------------------
_EN_WEB = [
    "I can't believe it's already {date} — we've been waiting for months, haven't we?",
    "The company's Q{n2} revenue hit ${money}M, up {n}% year-over-year, analysts said.",
    "Check out the state-of-the-art results at https://www.{dom}/paper (Smith et al., 2021).",
    "She said she'd email j.doe@{dom} by 5pm, but it's {time} and there's nothing yet.",
    "It was a well-known, hard-to-beat record: {n},{n2}00 points in a single game.",
    "Don't forget — the meeting's been moved to {date} at {n2}:30 a.m. sharp.",
    "You're gonna love this: the U.S. team won {n}-{n2} in overtime last night!",
    "We'll ship to the U.K. and the U.S.A. for $9.99; that's a 20%-off deal.",
]
# --- German prose templates (long, low special-char density) -------------------
_DE_PROSE = [
    "Das Unternehmen meldete im vierten Quartal einen Umsatz von rund vier Milliarden "
    "Euro und übertraf damit die Erwartungen der meisten Analysten deutlich.",
    "Die Forscherinnen und Forscher untersuchten über mehrere Jahre hinweg, wie sich "
    "veränderte Lebensbedingungen auf das Verhalten der untersuchten Population auswirken.",
    "Nach einer langen und kontrovers geführten Debatte einigten sich die Abgeordneten "
    "schließlich auf einen Kompromiss, der von allen Beteiligten mitgetragen werden konnte.",
    "Bitte senden Sie das vollständig ausgefüllte Dokument bis spätestens Freitag an die "
    "zuständige Abteilung, damit die Bearbeitung Ihres Antrags rechtzeitig erfolgen kann.",
    "Der Roman erzählt die Geschichte einer Familie über drei Generationen hinweg und "
    "verwebt dabei persönliche Schicksale mit den großen Umbrüchen des Jahrhunderts.",
    "Obwohl die Bedingungen alles andere als günstig waren, gelang es dem Team, das "
    "Projekt innerhalb des vorgesehenen Zeitrahmens und ohne nennenswerte Mehrkosten "
    "erfolgreich abzuschließen.",
]


def _fill(rng, template):
    return template.format(
        time=f"{rng.randint(0, 23)}:{rng.randint(0, 59):02d}",
        date=f"{rng.randint(1, 28)}.{rng.randint(1, 12)}.20{rng.randint(10, 23)}",
        money=f"{rng.randint(1, 9)}.{rng.randint(0, 999):03d},{rng.randint(0, 99):02d}",
        n=rng.randint(2, 999),
        n2=rng.randint(2, 24),
        dom=rng.choice(_DOMAINS),
        name=rng.choice(_NAMES),
        tag=rng.choice(_HASHTAGS),
        em=rng.choice(_EMOJI),
    )


def _emoji_paragraph(rng):
    words = ["OMG", "das", "ist", "sooo", "geil", "ich", "kann", "nicht", "mehr",
             "lol", "weiter", "gehts", "heute", "war", "der", "Hammer", "danke",
             "euch", "allen", "bis", "gleich", "ciao"]
    out = []
    for _ in range(rng.randint(6, 16)):
        out.append(rng.choice(words))
        if rng.random() < 0.45:
            out.append("".join(rng.choice(_EMOJI) for _ in range(rng.randint(1, 3))))
    return " ".join(out) + rng.choice(["", " ❤️", " \U0001f44d", "!!!"])


def make_corpus(name, n_paragraphs, seed=0):
    """Return a deterministic list of ``n_paragraphs`` paragraph strings."""
    if name not in CATEGORIES:
        raise ValueError(f"unknown corpus {name!r}; choose from {CATEGORIES}")
    # Stable, cross-process hash — NOT builtin hash() (salted by PYTHONHASHSEED).
    name_salt = int.from_bytes(hashlib.sha1(name.encode()).digest()[:4], "big")
    rng = random.Random(name_salt ^ seed)
    if name == "mixed":
        banks = [("de_cmc", _DE_CMC), ("en_web", _EN_WEB),
                 ("de_prose", _DE_PROSE), ("emoji", None)]
        out = []
        for i in range(n_paragraphs):
            cat, bank = banks[i % len(banks)]
            out.append(_emoji_paragraph(rng) if cat == "emoji"
                       else _fill(rng, rng.choice(bank)))
        return out
    if name == "emoji":
        return [_emoji_paragraph(rng) for _ in range(n_paragraphs)]
    bank = {"de_cmc": _DE_CMC, "en_web": _EN_WEB, "de_prose": _DE_PROSE}[name]
    return [_fill(rng, rng.choice(bank)) for _ in range(n_paragraphs)]


def corpus_stats(paragraphs):
    chars = sum(len(p) for p in paragraphs)
    return {"paragraphs": len(paragraphs), "chars": chars,
            "avg_len": chars / max(1, len(paragraphs))}


def xml_sample(n_paragraphs=200, seed=0):
    """Return one XML string with ``n_paragraphs`` <p> elements of de_cmc text."""
    paras = make_corpus("de_cmc", n_paragraphs, seed)
    body = "\n".join(f"  <p>{_xml_escape(p)}</p>" for p in paras)
    return f"<html>\n<body>\n{body}\n</body>\n</html>\n"


if __name__ == "__main__":
    for cat in CATEGORIES:
        c = make_corpus(cat, 5, seed=1)
        st = corpus_stats(make_corpus(cat, 1000, seed=1))
        print(f"# {cat}  (1000 paras: {st['chars']} chars, avg {st['avg_len']:.0f})")
        print("   " + c[0][:100])
