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

# Eyes/mouth emoticons + a textface literal set + heart. SoMaJo's *full* emoticon
# pattern (with its textual `:word:` rule) was ~1.4x slower in the combined regex
# for no extra F1 on the EmpiriST test set, so this is a curated equivalent.
_TEXTFACES = sorted(
    ["*<:-)", ":;-))", ":;))", "*_*", "._.", ">_<", "<_<", ">_>", "^.^", "^_^",
     "o.O", "O.o", "O_o", "T_T", "-_-", ":!:", "\\o/", "\\m/", "¬_¬", "ò_ó",
     "v.v", "ó.ò", ";_;", "._.", ">.<", "x.x", "n_n", "u.u"],
    key=len, reverse=True)
_EMOTICON_PART = (
    r"(?P<emoticon>(?:[:;=]|(?<!\d)8)[-'oO^]?(?:\)+|\(+|[DPp]+(?!\w)|[|/\\<>*]|\]+|\[+)"
    + r"|" + r"|".join(regex.escape(t) for t in _TEXTFACES)
    + r"|<3+|(?<![\w])[<^]3+(?!\d)|\^\^|x'?D+\b|:'[(C]|\\o/)")

# Abbreviation lexicon — kept as a SET for a cheap post-pass, NOT baked into the
# combined regex (a 1000+-literal alternation evaluated at every position made
# the single pass ~9x slower; the gate-then-set-lookup is what SoMaJo learned).
_ABBR = utils.read_abbreviation_file("abbreviations_de.txt", to_lower=True)
# A few high-frequency abbreviations EmpiriST keeps that are handled by
# context-specific rules in SoMaJo (not the plain lexicon).
_ABBR_SET = frozenset(_ABBR) | {"art.", "nr.", "abs."}
_ABBR_MAXLEN = max(len(a) for a in _ABBR_SET)
_LETTER_DOT = regex.compile(r"\p{L}\.")
# camelCase splitting (SoMaJo's --split_camel_case), WITH the exception lexicon
# that protects established names (WhatsApp, LaserJet, ...) — naive splitting
# without it crashes precision. Split before an uppercase preceded by 2+
# lowercase and followed by a lowercase; skip words in the exception set.
_CAMEL_EXC = frozenset(utils.read_abbreviation_file("camel_case_tokens.txt"))
_CAMEL_POS = regex.compile(r"(?<=\p{Ll}\p{Ll})\p{Lu}(?=\p{Ll})")
_INNEN = regex.compile(r"^\p{L}+\p{Ll}In(?:nen)?\p{Ll}*$")


def _camel_split(w):
    # cheap reject: no internal uppercase -> not camelCase. emojiQ<Name> is
    # EmpiriST's textual emoji encoding — one token, never split.
    if len(w) < 2 or w[1:].islower() or w in _CAMEL_EXC or w.startswith("emojiQ") or _INNEN.match(w):
        return (w,)
    pos = [m.start() for m in _CAMEL_POS.finditer(w)]
    if not pos:
        return (w,)
    parts = []
    prev = 0
    for p in pos:
        parts.append(w[prev:p])
        prev = p
    parts.append(w[prev:])
    return parts

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
    # emoticons: SoMaJo's full pattern (built above)
    _EMOTICON_PART,
    # emoji grapheme (pictographic, with ZWJ joins / skin tones / VS16)
    r"(?P<emoji>(?:\p{Extended_Pictographic}|\p{Regional_Indicator})(?:‍\p{Extended_Pictographic}|[\U0001f3fb-\U0001f3ff]|️|\p{Regional_Indicator})*)",
    # ellipsis
    r"(?P<ellipsis>\.{2,}|…+)",
    # structural abbreviations only (cheap): (L.){2,} like z.B., or single letter+dot.
    # Lexicon word-abbreviations (Bd., usw., ...) are recovered in a post-pass.
    r"(?P<abbr>(?:\p{L}\.){2,}|(?<![\p{L}.])\p{L}\.(?!\p{L}{1,3}\.))",
    # German decades: 1950er, 70ern, 1970er-Jahre — before the number rules
    r"(?P<decade>(?<!\w)\d+er(?:n|s)?(?:-\p{L}[\p{L}\p{N}]*)?(?=\W|$))",
    # section numbers: 1.1. 1.2.3. (kept whole, incl. trailing dot)
    r"(?P<section>(?<!\w)\d+(?:\.\d+)+\.?(?!\d))",
    # ordinals: small number + dot (1. 2. 11.), not part of a larger number
    r"(?P<ordinal>(?<!\w)(?:\d{1,3}|\d{5,})\.(?!\d))",
    # numbers / dates / times (digit groups joined by . , : — NOT / ; EmpiriST
    # splits "2009/2010" -> "2009" "/" "2010")
    r"(?P<number>(?<![\w])\d+(?:[.,:]\d+)*(?:[.,]-)?)",
    # leading-hyphen compound ellipsis: -ausrüstung, -mechanismen
    r"(?P<lhyphen>-\p{L}[\p{L}\p{N}'’´-]*)",
    # words: letters/digits joined by internal hyphen/apostrophe (incl. ´), with
    # an optional TRAILING hyphen for compound ellipsis (Kultur- und ...). Slash
    # is NOT internal — EmpiriST splits "gelöst/an" -> "gelöst" "/" "an".
    r"(?P<word>\p{L}[\p{L}\p{N}]*(?:[-'’´]\p{L}[\p{L}\p{N}]*)*-?)",
    # any remaining run of identical punctuation collapses to one token (?!? !!! etc.)
    r"(?P<punctrun>(?P<pr>[!?])(?P=pr)*)",
    # single leftover non-space char
    r"(?P<punct>\S)",
]

PATTERN = regex.compile("|".join(_PARTS))

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
    """Tokenize one non-alphabetic whitespace-token: regex, camelCase-split word
    matches, split multipart abbreviations, then re-join lexicon abbreviations."""
    toks = []
    types = []
    for m in PATTERN.finditer(w):
        g = m.group()
        t = m.lastgroup
        if t == "word":                                   # camelCase even with punctuation
            for part in _camel_split(g):
                toks.append(part)
                types.append("word")
        elif t == "abbr" and g.count(".") >= 2:           # multipart z.B. -> z. B.
            for p in _LETTER_DOT.findall(g):
                toks.append(p)
                types.append("abbr")
        else:
            toks.append(g)
            types.append(t)
    aset = _ABBR_SET
    out = []
    i = 0
    n = len(toks)
    while i < n:
        # lexicon word-abbreviation: word + '.' -> one token (Bd., usw., Vgl.)
        if (types[i] == "word" and i + 1 < n and toks[i + 1] == "."
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
        if w.isalpha():        # fast path: a plain word (camelCase rejected cheaply inside)
            out.extend(_camel_split(w))
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
