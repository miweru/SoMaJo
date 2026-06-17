# somajo-native — evaluated Rust acceleration (NOT shipped)

This is a PyO3/maturin proof-of-concept for moving SoMaJo's #1 raw hotspot —
the grapheme/emoji segmentation in `Tokenizer._split_emojis` — into Rust
(`unicode-segmentation` for UAX#29 graphemes, `icu_properties` for
Extended_Pictographic / Emoji_Presentation). It builds and works, but **it is
deliberately not wired into the tokenizer**, because it cannot reproduce the
`regex` module's emoji classification byte-for-byte.

## Why it is not used

`emoji_boundaries()` is exactly correct on the common cases (plain emoji, ZWJ
sequences, flags, skin-tone modifiers, VS16, ©®™). But an exhaustive
single-codepoint parity scan against the Python `regex` module found **689
codepoints** where ICU4X's `Extended_Pictographic` set is **broader** than the
`regex` module's — including common characters like ★ (U+2605) and ☉ (U+2609).
On any text containing one of those, the Rust path would split a token the
Python path keeps whole, i.e. it would **change tokenization output**.

Reproduce:

```bash
cd somajo-native && maturin develop --release
python parity_test.py        # reports the 689-codepoint divergence
```

The lesson is twofold:

1. **Unicode-table parity is the wall for a Rust port here**, not the
   regex features. Any crate's property tables track a Unicode version (and a
   definition) that must match the `regex` module's *exactly* — and the
   `regex` module updates its tables frequently (it is versioned by date).
   Matching it would mean shipping a hand-pinned snapshot and re-syncing on
   every `regex` release: a permanent lockstep-maintenance hazard for an
   exact-output tool.
2. **The corpus differential would have falsely passed** (the benchmark
   corpora contain no ★/☉), so a property-level exhaustive scan — not just
   the corpus gate — is required to trust a Unicode-sensitive rewrite.

## Context

After the pure-Python + mypyc work (see the `benchmarks/` harness and the
`perf/*` commits), `_split_emojis` is already gated down to ~2% of runtime on
typical text, and the orchestration that dominates the remaining time is
already compiled by mypyc. The matching itself (~4%) cannot move to a Rust
FSM engine because the rules use lookaround and backreferences. So even a
*correct* Rust emoji path would only help emoji-heavy text, for a real and
ongoing correctness/maintenance cost — which is why this stays an experiment.
