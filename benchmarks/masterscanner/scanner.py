#!/usr/bin/env python3
"""Master-scanner prototype: tokenize in ONE priority-ordered regex pass.

Instead of SoMaJo's ~60 sequential rule passes over a mutating token list, this
builds a single combined regex whose alternatives are ordered by priority and
tile the input left-to-right (each non-space char belongs to exactly one
match). That turns O(rules x tokens) into O(chars) — the "fewer passes" lever.

It is NOT byte-identical to SoMaJo (single-pass leftmost-longest != the
cascade's per-rule + locking semantics), so it is judged on token-boundary F1
against the EmpiriST gold standard (see measure_ms.py), not the differential.

Reuses SoMaJo's German abbreviation lexicon so the dot/abbreviation decision —
a big F1 factor — matches where possible.
"""

import regex

from somajo import utils

# Abbreviation lexicon — kept as a SET for a cheap post-pass, NOT baked into the
# combined regex (a 1000+-literal alternation evaluated at every position made
# the single pass ~9x slower; the gate-then-set-lookup is what SoMaJo learned).
_ABBR = utils.read_abbreviation_file("abbreviations_de.txt", to_lower=True)
# A few high-frequency abbreviations EmpiriST keeps that are handled by
# context-specific rules in SoMaJo (not the plain lexicon).
_ABBR_SET = frozenset(_ABBR) | {"art.", "nr.", "abs."}
_ABBR_MAXLEN = max(len(a) for a in _ABBR_SET)
_LETTER_DOT = regex.compile(r"\p{L}\.")
# NOTE: naive camelCase splitting (split before Upper-after-lower) was tried and
# REVERTED — it over-splits established names (WhatsApp, YouTube) that SoMaJo
# protects with a camel_case_tokens.txt exception lexicon, crashing CMC
# precision to ~93%. Replicating that lexicon is the kind of long-tail tuning
# the single-pass scanner is meant to avoid, so those ~5 errors are left.

# Priority order matters: earlier alternatives win at a given position.
_PARTS = [
    # markup
    r"(?P<xmltag><(?:/?[\p{L}_!?][^<>]*)>)",
    # arrows
    r"(?P<arrow>-+>|<-+|[←→↑↓])",
    # urls / email (greedy, must come before word/punct)
    r"(?P<url>(?:(?:https?|ftp|svn)://|(?:https?://)?www\.)[^\s<>]+[^\s<>.,;:!?)\"'])",
    r"(?P<url2>(?<![\w.])[\w./-]+\.(?i:de|com|org|net|edu|gov|info|eu|at|ch|tv|me|io)(?:/[^\s]*)?)",
    r"(?P<email>[\w.%+-]+@[\w.-]+\.\p{L}{2,})",
    # social
    r"(?P<mention>[@]\w+)",
    r"(?P<hashtag>(?<!\w)[#]\w(?:[\w-]*\w)?)",
    # emoticons (a pragmatic subset) + heart
    r"(?P<emoticon>(?:[:;=]|(?<!\d)8)[-'oO^]?(?:\)+|\(+|[DPp]+(?!\w)|[|/\\<>*]|\]+|\[+)|<3+|\^\^|:'\(|\\o/)",
    # emoji grapheme (pictographic, with ZWJ joins / skin tones / VS16)
    r"(?P<emoji>(?:\p{Extended_Pictographic}|\p{Regional_Indicator})(?:‍\p{Extended_Pictographic}|[\U0001f3fb-\U0001f3ff]|️|\p{Regional_Indicator})*)",
    # ellipsis
    r"(?P<ellipsis>\.{2,}|…+)",
    # structural abbreviations only (cheap): (L.){2,} like z.B., or single letter+dot.
    # Lexicon word-abbreviations (Bd., usw., ...) are recovered in a post-pass.
    r"(?P<abbr>(?:\p{L}\.){2,}|(?<![\p{L}.])\p{L}\.(?!\p{L}{1,3}\.))",
    # ordinals: small number + dot (1. 2. 11.), not part of a larger number
    r"(?P<ordinal>(?<!\w)(?:\d{1,3}|\d{5,})\.(?!\d))",
    # numbers / dates / times (one token: digit groups joined by . , : / -)
    r"(?P<number>(?<![\w])\d+(?:[.,:/]\d+)*(?:[.,]-)?)",
    # words: letters, may contain digits, joined by internal hyphen/apostrophe
    # (slash is NOT internal — EmpiriST splits "gelöst/an" -> "gelöst" "/" "an")
    r"(?P<word>\p{L}[\p{L}\p{N}]*(?:[-'’]\p{L}[\p{L}\p{N}]*)*)",
    # any remaining run of identical punctuation collapses to one token (?!? !!! etc.)
    r"(?P<punctrun>(?P<pr>[!?])(?P=pr)*)",
    # single leftover non-space char
    r"(?P<punct>\S)",
]

PATTERN = regex.compile("|".join(_PARTS))

# The url/url2/email alternatives greedily scan every word before failing — ~32%
# of the runtime — yet a url/email is possible only when the text contains one of
# `://`, `www.`, `@`, or `.<TLD>`. So compile a FAST pattern without them and gate
# Token-level gating: split each line on whitespace and emit pure-alphabetic
# whitespace-tokens directly (str.isalpha() is a cheap C call). The combined
# regex then runs ONLY on the ~20% of "interesting" tokens that contain
# something other than letters — the same idea as SoMaJo's per-rule gating, one
# level up. ~2.8x faster than scanning every line with the full regex, with
# identical output (no rule spans whitespace; a token's start is a whitespace
# boundary, so the lookbehinds see the same context).
#
# Assumption: markup tags sit on their own lines (true for the EmpiriST format).
# Inline tags containing spaces would be split by whitespace — a real fast-mode
# tokenizer would extract markup first.
_XMLTAG = regex.compile(r"<(?:/?[\p{L}_!?][^<>]*)>")


def _process_token(w):
    """Tokenize one non-alphabetic whitespace-token: regex + lexicon post-pass."""
    toks = []
    types = []
    for m in PATTERN.finditer(w):
        toks.append(m.group())
        types.append(m.lastgroup)
    aset = _ABBR_SET
    out = []
    i = 0
    n = len(toks)
    while i < n:
        # multipart abbreviation (z.B., i.d.R.) -> split into dotted parts (EmpiriST)
        if types[i] == "abbr" and toks[i].count(".") >= 2:
            out.extend(_LETTER_DOT.findall(toks[i]))
            i += 1
        # lexicon word-abbreviation: word + '.' -> one token (Bd., usw.)
        elif (types[i] == "word" and i + 1 < n and toks[i + 1] == "."
                and len(toks[i]) < _ABBR_MAXLEN and (toks[i] + ".").lower() in aset):
            out.append(toks[i] + ".")
            i += 2
        else:
            out.append(toks[i])
            i += 1
    return out


def _line_tokens(line):
    line = line.strip()
    if not line:
        return []
    if line[0] == "<" and line[-1] == ">" and _XMLTAG.fullmatch(line):
        return [line]
    out = []
    for w in line.split():
        if w.isalpha():        # fast path: a plain word, no further work
            out.append(w)
        else:
            out.extend(_process_token(w))
    return out


def tokenize(text):
    """Return a flat list of token strings for ``text``."""
    out = []
    for line in text.split("\n"):
        out.extend(_line_tokens(line))
    return out


def tokenize_lines(text):
    """Yield a list of tokens per non-empty line."""
    return [toks for line in text.split("\n") if (toks := _line_tokens(line))]
