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
| **master-scanner** | **15.2 M chars/s** | **99.27%** | 99.00% | 99.54% |
| SoMaJo (current build) | 0.89 M chars/s | 99.75% | 99.59% | 99.91% |
| | **17.2x faster** | **−0.48%** | | |

So: **~17x faster than the already-3.6x-optimised SoMaJo (≈61x over the
original single-core), for ~0.5 percentage points of F1** — i.e. the token
error rate roughly doubles (0.25% → 0.73%).

### How it got to 17x — two F1-preserving speed steps on top of the single pass

The naive combined-regex single pass was "only" 4.5x. Profiling showed 90% of
its time is the regex matching itself, and within that:

1. **url/email gating (1.4x).** The `url`/`url2`/`email` alternatives greedily
   scan *every word* before failing — ~32% of the time — yet a url/email is
   possible only when the text contains `://`, `www.`, `@`, or `.<TLD>`. Gate a
   url-free fast pattern behind that cheap necessary condition. ~95% of lines
   take the fast pattern; output is identical.
2. **token-level isalpha fast path (2.8x).** Split each line on whitespace and
   emit pure-alphabetic tokens directly (`str.isalpha()`, a C call) — 80% of
   tokens. The regex runs only on the ~20% "interesting" tokens. This is
   SoMaJo's own per-rule gating idea, one level up. Output is identical (no rule
   spans whitespace; a token start is a whitespace boundary, so the lookbehinds
   see the same context). Markup is assumed to sit on its own line.

(stdlib `re` was tried instead of the `regex` module — it is ~2.4x *slower*
here; a second `.`-presence gate gave only ~1.02x and was dropped.)

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

This is the first genuine 2x+ lever found, and it is real: ~17x for ~0.5% F1.
But SoMaJo's entire value proposition is being the *most accurate* CMC tokenizer
(EmpiriST winner), so silently trading 0.5% F1 for speed would undercut that.
The responsible packaging is an **opt-in fast mode** (e.g. `SoMaJo(..., fast=True)`
or a separate `FastTokenizer`) for throughput-bound users who can accept
near-gold accuracy — not a replacement for the exact, accuracy-first default.
The decision is the maintainer's; this prototype makes it a measured one.
