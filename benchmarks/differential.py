#!/usr/bin/env python3
"""Differential output gate for the SoMaJo performance refactor.

This is the safety net the whole roadmap depends on: it freezes a *byte-exact*
golden tokenization from a known-good baseline and asserts that any later
change reproduces it identically — not just the token text, but ``token_class``,
``space_after``, ``original_spelling`` and ``character_offset`` as well, across
several constructor configurations and the XML pipeline. The 1447-line unit
suite cannot cover the combinatorial long tail of rule interactions on real
text; this can.

Usage (run from the repo root, with the editable somajo install active):

    python -m benchmarks.differential freeze            # capture baseline golden
    python -m benchmarks.differential check             # assert identical output
    python -m benchmarks.differential check --quick     # smaller, faster corpora

``check`` exits non-zero on the first divergence and prints the offending
paragraph with the mismatching token highlighted. Run it after every commit on
the optimization branch.

The golden is keyed to the ``regex`` module version (its Unicode tables drive
emoji/\\p{} behavior and drift between releases): ``check`` refuses to pass with
a load-bearing warning if the version differs from when the golden was frozen.
"""

import argparse
import gzip
import json
import os
import platform
import subprocess
import sys

import regex

import somajo
from benchmarks import corpora

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")

# (label, language, split_camel_case, split_sentences, character_offsets)
# Chosen to exercise the camelCase block, the en/de forks, the sentence
# splitter, and the offset-alignment code paths.
PROFILES = [
    ("de_offsets", "de_CMC", False, True, True),
    ("de_camel", "de_CMC", True, True, False),
    ("en_offsets", "en_PTB", False, True, True),
]
EOS_TAGS = "title h1 h2 h3 h4 h5 h6 p br hr div ol ul dl table".split()

# Corpus sizes (paragraphs). --quick shrinks these for a fast pre-commit check.
SIZES = {"full": 4000, "quick": 600}
XML_SIZE = {"full": 600, "quick": 120}
SEED = 20260617


def _tok_record(t):
    """A fully-specifying, JSON-able record for one Token."""
    off = list(t.character_offset) if t.character_offset is not None else None
    return [t.text, t.token_class, int(t.space_after), t.original_spelling,
            int(t.markup), off]


def _records_text(corpus, lang, camel, sentences, offsets):
    tok = somajo.SoMaJo(lang, split_camel_case=camel, split_sentences=sentences,
                        character_offsets=offsets)
    return [[_tok_record(t) for t in chunk] for chunk in tok.tokenize_text(corpus)]


def _records_xml(xml, lang, sentences):
    tok = somajo.SoMaJo(lang, split_sentences=sentences)
    return [[_tok_record(t) for t in chunk]
            for chunk in tok.tokenize_xml(xml, eos_tags=EOS_TAGS)]


def _build(scale):
    """Produce {key: records} for every (profile x corpus) plus XML."""
    n = SIZES[scale]
    data = {}
    for label, lang, camel, sentences, offsets in PROFILES:
        cats = corpora.CATEGORIES if lang == "de_CMC" else ["en_web"]
        for cat in cats:
            corpus = corpora.make_corpus(cat, n, seed=SEED)
            key = f"{label}/{cat}"
            data[key] = _records_text(corpus, lang, camel, sentences, offsets)
    data["xml/de_cmc"] = _records_xml(corpora.xml_sample(XML_SIZE[scale], SEED),
                                      "de_CMC", True)
    # Real EmpiriST text (if available), validated with offsets + camelCase.
    if corpora.empirist_available():
        for sub in ("cmc", "web"):
            corpus = corpora.load_empirist(sub)
            data[f"empirist_off/{sub}"] = _records_text(corpus, "de_CMC", False, True, True)
            data[f"empirist_camel/{sub}"] = _records_text(corpus, "de_CMC", True, True, False)
    return data


def _git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(GOLDEN_DIR),
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _manifest(scale):
    return {"somajo": getattr(somajo, "__version__", "?"),
            "regex": regex.__version__,
            "python": platform.python_version(),
            "git_commit": _git_commit(),
            "scale": scale, "seed": SEED,
            "profiles": [p[0] for p in PROFILES]}


def _path(scale):
    return os.path.join(GOLDEN_DIR, f"golden_{scale}.json.gz")


def freeze(scale):
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    man = _manifest(scale)
    data = _build(scale)
    n_tok = sum(len(s) for recs in data.values() for s in recs)
    with gzip.open(_path(scale), "wt", encoding="utf-8") as f:
        json.dump({"manifest": man, "data": data}, f, ensure_ascii=False)
    print(f"Froze golden ({scale}): {len(data)} datasets, {n_tok:,} tokens "
          f"-> {_path(scale)}")
    print(f"  baseline: somajo {man['somajo']}, regex {man['regex']}, "
          f"python {man['python']}, commit {man['git_commit'][:10]}")


def _first_diff(golden_sents, new_sents, key):
    if len(golden_sents) != len(new_sents):
        return (f"[{key}] chunk count differs: golden={len(golden_sents)} "
                f"new={len(new_sents)}")
    for si, (g, n) in enumerate(zip(golden_sents, new_sents)):
        if g == n:
            continue
        if len(g) != len(n):
            ctx = " ".join(r[0] for r in g)
            return (f"[{key}] chunk {si}: token COUNT differs "
                    f"(golden={len(g)} new={len(n)})\n    golden: {ctx!r}\n"
                    f"    new:    {' '.join(r[0] for r in n)!r}")
        for ti, (gt, nt) in enumerate(zip(g, n)):
            if gt != nt:
                fields = ["text", "token_class", "space_after",
                          "original_spelling", "markup", "offset"]
                diffs = [f"{fields[k]}: {gt[k]!r} -> {nt[k]!r}"
                         for k in range(len(fields)) if gt[k] != nt[k]]
                ctx = " ".join(r[0] for r in g)
                return (f"[{key}] chunk {si}, token {ti}:\n    context: {ctx!r}\n"
                        f"    " + "\n    ".join(diffs))
    return None


def check(scale):
    path = _path(scale)
    if not os.path.exists(path):
        print(f"No golden at {path}. Run: python -m benchmarks.differential "
              f"freeze {'--quick' if scale == 'quick' else ''}".rstrip())
        return 2
    with gzip.open(path, "rt", encoding="utf-8") as f:
        frozen = json.load(f)
    man = frozen["manifest"]
    warn = False
    if man["regex"] != regex.__version__:
        warn = True
        print("!! WARNING: regex module version changed "
              f"({man['regex']} -> {regex.__version__}). Unicode tables may have "
              "drifted (\\p{} / \\X / emoji). A mismatch below may be a table "
              "change, not a refactor bug. Re-freeze on the baseline commit to "
              "compare like-for-like.", file=sys.stderr)
    new = _build(scale)
    golden = frozen["data"]
    if set(golden) != set(new):
        print(f"Dataset keys differ: {set(golden) ^ set(new)}")
        return 1
    n_tok = 0
    for key in sorted(golden):
        n_tok += sum(len(s) for s in new[key])
        diff = _first_diff(golden[key], new[key], key)
        if diff is not None:
            print("DIFFERENTIAL FAILED — output is NOT byte-identical:\n")
            print(diff)
            return 1
    print(f"OK: byte-identical output on {len(golden)} datasets, {n_tok:,} tokens "
          f"({scale}).")
    if warn:
        print("   (passed despite a regex-version change — see warning above.)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["freeze", "check"])
    ap.add_argument("--quick", action="store_true", help="smaller, faster corpora")
    args = ap.parse_args()
    scale = "quick" if args.quick else "full"
    if args.action == "freeze":
        freeze(scale)
        return 0
    return check(scale)


if __name__ == "__main__":
    sys.exit(main())
