# SoMaJo performance harness (Stage 0)

The safety net + measuring tape for the performance refactor. Two rules:

1. **Never** land a perf change without `differential check` passing.
2. **Never** report a speedup without re-running `benchmark` for the number.

Run everything from the repo root with the editable `somajo` install active.

## Differential output gate — `differential.py`

Freezes a *byte-exact* golden tokenization (text **and** `token_class`,
`space_after`, `original_spelling`, `character_offset`, markup) across several
constructor configurations (de/en, camelCase on/off, offsets on/off) and the
XML pipeline, then asserts later code reproduces it identically.

```bash
python -m benchmarks.differential freeze          # once, on a known-good baseline
python -m benchmarks.differential check           # after every perf commit
python -m benchmarks.differential check --quick   # fast pre-commit variant
```

`check` exits non-zero on the first divergence and prints the offending
paragraph with the exact field that changed. The golden is keyed to the `regex`
module version (its Unicode tables drive `\p{}` / `\X` / emoji behavior); `check`
warns loudly if that version drifted, because then a mismatch may be a table
change rather than a refactor bug. Golden files live in `golden/` (gitignored) —
regenerate with `freeze` from the baseline commit.

## Throughput benchmark — `benchmark.py`

Reports chars/s **and** tokens/s (warm, best-of-N) per corpus, single- and
multi-core.

```bash
python -m benchmarks.benchmark
python -m benchmarks.benchmark --parallel
python -m benchmarks.benchmark --n 8000 --runs 5
```

## Corpora — `corpora.py`

Deterministic, seed-stable generators stressing different rule clusters:
`de_cmc`, `en_web`, `de_prose` (common-path heavy), `emoji` (#1 hotspot),
`mixed`, plus an XML sample. `python -m benchmarks.corpora` prints samples.

> Numbers are only comparable on the same machine / Python / `regex` build.
> Pair every speed claim with a passing differential check.
