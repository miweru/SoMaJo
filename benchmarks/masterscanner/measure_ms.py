#!/usr/bin/env python3
"""Measure the master-scanner: token-boundary F1 (vs EmpiriST gold) + speed."""

import contextlib
import importlib.util
import io
import os
import tempfile
import time

import scanner

import somajo
from benchmarks import corpora

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_GOLD = os.path.join(_ROOT, "data", "empirist_gold_standard")
_EVAL_PY = os.path.join(_ROOT, "utils", "evaluate.py")


def _ev():
    spec = importlib.util.spec_from_file_location("_ev", _EVAL_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def f1(subcorpus):
    ev = _ev()
    raw_dir = os.path.join(_GOLD, f"test_{subcorpus}", "raw")
    gold_dir = os.path.join(_GOLD, f"test_{subcorpus}", "tokenized")
    names = sorted(os.listdir(raw_dir))
    tp = fp = fn = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            with open(os.path.join(raw_dir, name), encoding="utf-8") as fh:
                text = fh.read()
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as out:
                for toks in scanner.tokenize_lines(text):
                    for t in toks:
                        out.write(t + "\n")
        for name in names:
            with contextlib.redirect_stdout(io.StringIO()):
                r = ev.evaluate_file(os.path.join(tmp, name), os.path.join(gold_dir, name),
                                     ignore_xml=True, sentences=False, error_file=None)
            tp += r[0]; fp += r[1]; fn += r[2]
    return ev.precision_recall_f1(tp, fp, fn)


def speed():
    paras = (corpora.load_empirist("web", n=4000, seed=1)
             + corpora.load_empirist("cmc", n=4000, seed=1))
    chars = sum(len(p) for p in paras)
    # master-scanner
    for _ in range(2):
        [scanner.tokenize(p) for p in paras[:200]]
    best_ms = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        n_ms = sum(len(scanner.tokenize(p)) for p in paras)
        best_ms = min(best_ms, time.perf_counter() - t0)
    # SoMaJo (current optimized build), tokenization only (no sentence splitting,
    # for a fair single-pass comparison)
    tok = somajo.SoMaJo("de_CMC", split_sentences=False)
    list(tok.tokenize_text(paras[:200]))
    best_sj = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        n_sj = sum(len(s) for s in tok.tokenize_text(paras))
        best_sj = min(best_sj, time.perf_counter() - t0)
    return chars, best_ms, n_ms, best_sj, n_sj


def main():
    print("=== F1 vs EmpiriST gold (master-scanner) ===")
    fs = []
    for sub in ("cmc", "web"):
        p, r, f = f1(sub)
        fs.append(f)
        print(f"  empirist_{sub}: P={p * 100:6.2f}%  R={r * 100:6.2f}%  F={f * 100:6.2f}%"
              f"   (SoMaJo: {'99.59' if sub == 'cmc' else '99.91'}%)")
    print(f"  mean F = {sum(fs) / len(fs) * 100:.2f}%   (SoMaJo mean 99.75%)\n")

    print("=== Speed (tokenization only, real EmpiriST text) ===")
    chars, t_ms, n_ms, t_sj, n_sj = speed()
    print(f"  master-scanner: {t_ms:.3f}s  {chars / t_ms / 1e6:.3f} M chars/s  ({n_ms} tokens)")
    print(f"  SoMaJo:         {t_sj:.3f}s  {chars / t_sj / 1e6:.3f} M chars/s  ({n_sj} tokens)")
    print(f"  >>> master-scanner is {t_sj / t_ms:.2f}x faster")


if __name__ == "__main__":
    main()
