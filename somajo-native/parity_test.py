#!/usr/bin/env python3
"""Parity test: Rust ``emoji_boundaries`` vs the Python ``_split_emojis`` logic.

Demonstrates why the Rust emoji accelerator is not shipped: ICU4X's emoji
property tables diverge from the ``regex`` module's on hundreds of codepoints.

Run after ``maturin develop --release`` in this directory.
"""

import regex as re

import somajo_native

# The exact predicates from Tokenizer._split_emojis.
_trigger = re.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}️]")
_single = re.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}]")
_grapheme = re.compile(r"\X")


def py_boundaries(text):
    out = []
    for m in _grapheme.finditer(text):
        g = m.group()
        if m.end() - m.start() > 1:
            if _trigger.search(g):
                out.append((m.start(), m.end()))
        elif _single.search(g):
            out.append((m.start(), m.end()))
    return out


def main():
    cases = [
        "Hallo 😀 Welt", "© 2020 ™ ®", "‼️ wow", "👨‍👩‍👧‍👦", "🇩🇪", "👍🏻",
        "❤️", "☀️⭐✅", "a😍b😂c", "🤷‍♂️", "🏳️‍🌈", "1️⃣", "😀😀😀", "déjà vu",
    ]
    case_fails = [c for c in cases if py_boundaries(c) != somajo_native.emoji_boundaries(c)]
    print(f"hand-picked cases: {len(cases) - len(case_fails)}/{len(cases)} match"
          + (f"  MISMATCH: {case_fails}" if case_fails else ""))

    ranges = list(range(0x80, 0x3300)) + list(range(0x1F000, 0x1FB00))
    mism = [cp for cp in ranges
            if bool(_single.search(chr(cp))) != bool(somajo_native.emoji_boundaries(chr(cp)))]
    print(f"exhaustive single-codepoint scan ({len(ranges)} codepoints): "
          f"{len(mism)} mismatches")
    for cp in mism[:10]:
        c = chr(cp)
        print(f"  U+{cp:04X} {c!r}: regex={bool(_single.search(c))} "
              f"icu/rust={bool(somajo_native.emoji_boundaries(c))}")
    print("\nConclusion: NOT byte-identical -> not shippable (see README.md)."
          if mism else "\nByte-identical on the scanned range.")


if __name__ == "__main__":
    main()
