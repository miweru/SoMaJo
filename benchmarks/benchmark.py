#!/usr/bin/env python3
"""Throughput benchmark for SoMaJo.

Reports both chars/s and tokens/s (warm runs, best of N) per corpus, single-core
and multi-core, so a refactor can be judged on the metric that matters for the
workload. Run from the repo root:

    python -m benchmarks.benchmark                 # default corpora, single-core
    python -m benchmarks.benchmark --parallel      # also measure multi-core scaling
    python -m benchmarks.benchmark --n 8000 --runs 5

Numbers are only comparable on the same machine/Python/regex build. Always pair
a speed claim with `python -m benchmarks.differential check` to prove the output
did not change.
"""

import argparse
import os
import time

import regex
import somajo
from benchmarks import corpora

SEED = 20260617


def _consume(tok, paragraphs, parallel=1):
    n_tokens = 0
    for chunk in tok.tokenize_text(paragraphs, parallel=parallel):
        n_tokens += len(chunk)
    return n_tokens


def _best(fn, runs):
    best = float("inf")
    n = 0
    for _ in range(runs):
        t0 = time.perf_counter()
        n = fn()
        best = min(best, time.perf_counter() - t0)
    return best, n


def run(cats, n, runs, parallel):
    print(f"# SoMaJo {getattr(somajo, '__version__', '?')} | regex "
          f"{regex.__version__} | py {os.sys.version.split()[0]} | "
          f"{os.cpu_count()} cores")
    print(f"# {n} paragraphs/corpus, best of {runs} warm runs\n")
    header = f"{'corpus':<10} {'chars':>9} {'tokens':>9} {'time(s)':>8} " \
             f"{'Mchars/s':>9} {'ktok/s':>8} {'kpar/s':>8}"
    print(header)
    print("-" * len(header))
    totals = {"chars": 0, "tokens": 0, "time": 0.0}
    for cat in cats:
        lang = corpora.LANG_OF[cat]
        paragraphs = corpora.make_corpus(cat, n, seed=SEED)
        chars = corpora.corpus_stats(paragraphs)["chars"]
        tok = somajo.SoMaJo(lang, split_sentences=True)
        _consume(tok, paragraphs[: min(200, n)])  # warm caches/compile
        dt, ntok = _best(lambda: _consume(tok, paragraphs), runs)
        totals["chars"] += chars
        totals["tokens"] += ntok
        totals["time"] += dt
        print(f"{cat:<10} {chars:>9} {ntok:>9} {dt:>8.3f} "
              f"{chars/dt/1e6:>9.3f} {ntok/dt/1e3:>8.1f} {n/dt/1e3:>8.2f}")
    tt = totals["time"]
    print("-" * len(header))
    print(f"{'TOTAL':<10} {totals['chars']:>9} {totals['tokens']:>9} {tt:>8.3f} "
          f"{totals['chars']/tt/1e6:>9.3f} {totals['tokens']/tt/1e3:>8.1f}")

    if parallel:
        print("\n# Multi-core scaling (mixed corpus)")
        ncores = os.cpu_count() or 1
        for size in (300, n, max(n, 20000)):
            paragraphs = corpora.make_corpus("mixed", size, seed=SEED)
            tok = somajo.SoMaJo("de_CMC", split_sentences=True)
            _consume(tok, paragraphs[:200])
            dt1, _ = _best(lambda: _consume(tok, paragraphs, parallel=1), runs)
            dtp, _ = _best(lambda: _consume(tok, paragraphs, parallel=ncores), runs)
            print(f"  {size:>6} paras: 1-core {dt1:.3f}s | {ncores}-core {dtp:.3f}s "
                  f"| speedup {dt1/dtp:>4.2f}x"
                  + ("   <-- parallel REGRESSION (pickling/spawn > work)"
                     if dt1 / dtp < 1 else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=4000, help="paragraphs per corpus")
    ap.add_argument("--runs", type=int, default=3, help="warm runs (reports best)")
    ap.add_argument("--corpora", nargs="*", default=corpora.CATEGORIES)
    ap.add_argument("--parallel", action="store_true",
                    help="also measure multi-core scaling")
    args = ap.parse_args()
    run(args.corpora, args.n, args.runs, args.parallel)


if __name__ == "__main__":
    main()
