# Master-scanner prototype — the "fewer passes" lever, measured

A single-pass tokenizer: one priority-ordered combined regex tiles the input
left-to-right (each non-space char belongs to exactly one match), plus a cheap
post-pass for lexicon abbreviations. This replaces SoMaJo's ~60 sequential rule
passes — the only remaining lever that changes the *real* tokenization (so it is
judged on F1 against the EmpiriST gold standard, not the differential).

Run: `PYTHONPATH=benchmarks/masterscanner:. python benchmarks/masterscanner/measure_ms.py`
(needs the gold data at `data/empirist_gold_standard/`).

## Result — the speed/accuracy trade, on real data

| | speed | F1 mean | F1 cmc | F1 web |
|---|---|---|---|---|
| **master-scanner** | **4.09 M chars/s** | **99.27%** | 99.00% | 99.54% |
| SoMaJo (current build) | 0.90 M chars/s | 99.75% | 99.59% | 99.91% |
| | **4.54x faster** | **−0.48%** | | |

So: **~4.5x faster than the already-3.6x-optimised SoMaJo (≈16x over the
original), for ~0.5 percentage points of F1** — i.e. the token error rate
roughly doubles (0.25% → 0.73%).

## What the build taught us

1. **The single-pass concept works dramatically** — but only after the right
   structure. A first version that baked the 1000+-entry abbreviation lexicon
   into the combined regex ran at 0.53 M chars/s — *slower than SoMaJo* —
   because that giant alternation is evaluated at every position. Moving it out
   (structural `(?:\p{L}\.){2,}` in the regex + a set-lookup post-pass that
   re-joins `word`+`.`) took it to ~5 M chars/s. This is exactly the lesson
   SoMaJo's own gating embodies: never run a big lexicon alternation everywhere.
2. **Most of the F1 gap is reducible long-tail tuning**: multipart abbreviations
   (`z.B.` → `z.` `B.`), ordinals (`1.`), arrows (`->`), slash splitting, and a
   handful of abbreviations were fixed cheaply (99.03% → 99.27%). The rest —
   rare emoticons (`:!:`, `*<:-)`), compound-ellipsis hyphens (`Kultur-`), and
   camelCase — is the kind of decade-of-tuning edge cases the cascade exists for.
3. **camelCase needs an exception lexicon**: naive "split before Upper-after-
   lower" over-splits established names (WhatsApp, YouTube) and crashed CMC
   precision to ~93%. SoMaJo protects them with camel_case_tokens.txt. Reverted.

## Verdict

This is the first genuine 2x+ lever found, and it is real: ~4.5x for ~0.5% F1.
But SoMaJo's entire value proposition is being the *most accurate* CMC tokenizer
(EmpiriST winner), so silently trading 0.5% F1 for speed would undercut that.
The responsible packaging is an **opt-in fast mode** (e.g. `SoMaJo(..., fast=True)`
or a separate `FastTokenizer`) for throughput-bound users who can accept
near-gold accuracy — not a replacement for the exact, accuracy-first default.
The decision is the maintainer's; this prototype makes it a measured one.
