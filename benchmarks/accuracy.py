#!/usr/bin/env python3
"""Tokenization accuracy (token-boundary F1) on the EmpiriST 2015 gold standard.

This is the yardstick for any change that is NOT byte-identical (e.g. a
master-scanner rewrite or an aggressive relaxation): it measures the real
accuracy delta against the manually-annotated gold standard, the metric SoMaJo
is actually judged on — so speed-for-accuracy trades can be decided on data, not
guesswork.

It reproduces the official eval (utils/evaluate_on_test_*.sh): tokenize each raw
test file the way `somajo-tokenizer --split_camel_case` does, then compare token
boundaries against the gold tokenization with utils/evaluate.py.

Requires the gold data at data/empirist_gold_standard/ (raw + tokenized for
test_cmc and test_web). Obtain it from a checkout of KorAP/KorAP-Tokenizer
(src/test/resources/empirist_gold_standard) or the original EmpiriST archive.

Usage:
    python -m benchmarks.accuracy            # both subcorpora, prints P/R/F
    python -m benchmarks.accuracy --quiet    # just the F numbers (for diffing)
"""

import argparse
import contextlib
import importlib.util
import io
import os
import tempfile

from somajo import SoMaJo

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_GOLD = os.path.join(_ROOT, "data", "empirist_gold_standard")
_EVAL_PY = os.path.join(_ROOT, "utils", "evaluate.py")


def _load_evaluate():
    spec = importlib.util.spec_from_file_location("_somajo_evaluate", _EVAL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def available():
    return os.path.isdir(_GOLD) and os.path.exists(_EVAL_PY)


def _tokenize_file(tok, raw_path, out_path):
    """Mirror `somajo-tokenizer --split_camel_case FILE`: one token per line."""
    with open(raw_path, encoding="utf-8") as f:
        # default CLI paragraph separator is empty_lines
        sentences = tok.tokenize_text_file(f, paragraph_separator="empty_lines")
        with open(out_path, "w", encoding="utf-8") as out:
            for sentence in sentences:
                for token in sentence:
                    out.write(token.text + "\n")


def evaluate(subcorpus, somajo=None):
    """Return (precision, recall, f1) for 'cmc' or 'web' on the test set."""
    ev = _load_evaluate()
    tok = somajo or SoMaJo("de_CMC", split_camel_case=True, split_sentences=True)
    raw_dir = os.path.join(_GOLD, f"test_{subcorpus}", "raw")
    gold_dir = os.path.join(_GOLD, f"test_{subcorpus}", "tokenized")
    with tempfile.TemporaryDirectory() as tmp:
        names = sorted(os.listdir(raw_dir))
        for name in names:
            _tokenize_file(tok, os.path.join(raw_dir, name), os.path.join(tmp, name))
        tp = fp = fn = 0
        for name in names:
            with contextlib.redirect_stdout(io.StringIO()):  # evaluate_file is chatty
                r = ev.evaluate_file(os.path.join(tmp, name), os.path.join(gold_dir, name),
                                     ignore_xml=True, sentences=False, error_file=None)
            tp += r[0]
            fp += r[1]
            fn += r[2]
    return ev.precision_recall_f1(tp, fp, fn)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if not available():
        print(f"Gold data not found at {_GOLD}. See module docstring.")
        return 2
    tok = SoMaJo("de_CMC", split_camel_case=True, split_sentences=True)
    fs = []
    for sub in ("cmc", "web"):
        p, r, f = evaluate(sub, tok)
        fs.append(f)
        if args.quiet:
            print(f"{sub}\tF={f * 100:.3f}")
        else:
            print(f"empirist_{sub}: P={p * 100:6.2f}%  R={r * 100:6.2f}%  F={f * 100:6.2f}%")
    if not args.quiet:
        print(f"mean F = {sum(fs) / len(fs) * 100:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
