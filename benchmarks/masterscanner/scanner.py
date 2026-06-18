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


def tokenize(text):
    """Return a flat list of token strings for ``text``: one regex pass + a cheap
    lexicon post-pass that re-joins ``word`` + ``.`` into a known abbreviation."""
    toks = []
    types = []
    for m in PATTERN.finditer(text):
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


def tokenize_lines(text):
    """Tokenize keeping line structure: yield a list of tokens per non-empty line.
    XML-tag-only lines are passed through unchanged (matches the EmpiriST format).
    """
    out = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        out.append(tokenize(line))
    return out
