#!/usr/bin/env python3
"""A fast, single-pass tokenizer — the opt-in ``fast=True`` mode of SoMaJo.

Instead of the cascade's ~60 sequential rule passes over a mutating token list,
this tiles each line with ONE priority-ordered combined regex (every non-space
character belongs to exactly one match), gated by a cheap ``str.isalpha()``
fast path so the regex only runs on the ~20 % of tokens that are not plain
words. A small post-pass re-joins lexicon abbreviations, splits multipart ones
(``z.B.`` → ``z.`` ``B.``) and applies camelCase splitting with SoMaJo's
exception lexicon.

It is roughly an order of magnitude faster than the exact tokenizer but is NOT
byte-identical: on the EmpiriST 2015 gold standard it scores ~99.5–99.8 % token
F1 vs ~99.6–99.9 % for the exact tokenizer (within ~0.1 pp). Use it for
throughput-bound work over large corpora where near-gold accuracy is enough;
use the default exact tokenizer when every token must match.

Tuned and measured for German (``de_CMC``); ``en_PTB`` runs but is less tuned.
Does not support ``character_offsets`` or the XML pipeline.
"""

import regex

from . import utils
from .token import Token

# --- emoticons: eyes/mouth + a curated textface set + heart ------------------
_TEXTFACES = sorted(
    ["*<:-)", ":;-))", ":;))", "*_*", "._.", ">_<", "<_<", ">_>", "^.^", "^_^",
     "o.O", "O.o", "O_o", "T_T", "-_-", ":!:", "\\o/", "\\m/", "¬_¬", "ò_ó",
     "v.v", "ó.ò", ";_;", ">.<", "x.x", "n_n", "u.u"],
    key=len, reverse=True)
_EMOTICON_PART = (
    r"(?P<emoticon>(?:[:;=]|(?<!\d)8)[-'oO^]?(?:\)+|\(+|[DPp]+(?!\w)|[|/\\<>*]|\]+|\[+)"
    + r"|" + r"|".join(regex.escape(t) for t in _TEXTFACES)
    + r"|<3+|(?<![\w])[<^]3+(?!\d)|\^\^|x'?D+\b|:'[(C]|\\o/)")

# --- camelCase (with the exception lexicon that protects WhatsApp, LaserJet) --
_CAMEL_EXC = frozenset(utils.read_abbreviation_file("camel_case_tokens.txt"))
_CAMEL_POS = regex.compile(r"(?<=\p{Ll}\p{Ll})\p{Lu}(?=\p{Ll})")
_INNEN = regex.compile(r"^\p{L}+\p{Ll}In(?:nen)?\p{Ll}*$")
_LETTER_DOT = regex.compile(r"\p{L}\.")


def _camel_split(w):
    # cheap reject: no internal uppercase -> not camelCase. emojiQ<Name> is
    # EmpiriST's textual emoji encoding — one token, never split.
    if (len(w) < 2 or w[1:].islower() or w in _CAMEL_EXC
            or w.startswith("emojiQ") or _INNEN.match(w)):
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


# --- the combined scanner (priority order matters) ---------------------------
_PARTS = [
    r"(?P<xmltag><(?:/?[\p{L}_!?][^<>]*)>)",
    r"(?P<arrow>-+>|<-+|[←→↑↓])",
    r"(?P<url>(?:(?:https?|ftp|svn)://|(?:https?://)?www\.)[^\s<>]+[^\s<>.,;:!?)\"'])",
    r"(?P<url2>(?<![\w.])[\w./-]+\.(?i:de|com|org|net|edu|gov|info|eu|at|ch|tv|me|io)(?:/[^\s]*)?)",
    r"(?P<email>[\w.%+-]+@[\w.-]+\.\p{L}{2,})",
    r"(?P<mention>[@]\w+)",
    r"(?P<hashtag>(?<!\w)[#]\w(?:[\w-]*\w)?)",
    _EMOTICON_PART,
    r"(?P<emoji>(?:\p{Extended_Pictographic}|\p{Regional_Indicator})(?:‍\p{Extended_Pictographic}|[\U0001f3fb-\U0001f3ff]|️|\p{Regional_Indicator})*)",
    r"(?P<ellipsis>\.{2,}|…+)",
    r"(?P<abbr>(?:\p{L}\.){2,}|(?<![\p{L}.])\p{L}\.(?!\p{L}{1,3}\.))",
    r"(?P<decade>(?<!\w)\d+er(?:n|s)?(?:-\p{L}[\p{L}\p{N}]*)?(?=\W|$))",
    r"(?P<section>(?<!\w)\d+(?:\.\d+)+\.(?!\d))",  # 1.1. 1.2.3. — trailing dot required (so 1.999,95 stays a number)
    r"(?P<ordinal>(?<!\w)(?:\d{1,3}|\d{5,})\.(?!\d))",
    r"(?P<number>(?<![\w])\d+(?:[.,:]\d+)*(?:[.,]-)?)",
    r"(?P<lhyphen>-\p{L}[\p{L}\p{N}'’´-]*)",
    r"(?P<word>\p{L}[\p{L}\p{N}]*(?:[-'’´]\p{L}[\p{L}\p{N}]*)*-?)",
    r"(?P<punctrun>(?P<pr>[!?])(?P=pr)*)",
    r"(?P<punct>\S)",
]
_PATTERN = regex.compile("|".join(_PARTS))
_XMLTAG = regex.compile(r"<(?:/?[\p{L}_!?][^<>]*)>")

# scanner group name -> SoMaJo token class
_TYPE2CLASS = {
    "arrow": "symbol", "url": "URL", "url2": "URL", "email": "email_address",
    "mention": "mention", "hashtag": "hashtag", "emoticon": "emoticon",
    "emoji": "emoticon", "ellipsis": "symbol", "abbr": "abbreviation",
    "decade": "number", "section": "number", "ordinal": "ordinal",
    "number": "number", "lhyphen": "regular", "word": "regular",
    "punctrun": "symbol", "punct": "symbol",
}


class FastTokenizer:
    """Single-pass tokenizer producing ``Token`` objects. Use via
    ``SoMaJo(language, fast=True)``."""

    def __init__(self, language="de_CMC", split_camel_case=True):
        self.language = language
        self.split_camel_case = split_camel_case
        abbrev = utils.read_abbreviation_file(
            f"abbreviations_{language[:2]}.txt", to_lower=True)
        # a few frequent abbreviations EmpiriST keeps via context-specific rules
        self._abbr_set = frozenset(abbrev) | {"art.", "nr.", "abs."}
        self._abbr_maxlen = max(len(a) for a in self._abbr_set)

    def _process(self, w):
        """Tokenize one non-alphabetic whitespace-token -> list of (text, type)."""
        toks = []
        for m in _PATTERN.finditer(w):
            g = m.group()
            t = m.lastgroup
            if t == "word" and self.split_camel_case:
                toks.extend((part, "word") for part in _camel_split(g))
            elif t == "abbr" and g.count(".") >= 2:
                toks.extend((p, "abbr") for p in _LETTER_DOT.findall(g))
            else:
                toks.append((g, t))
        aset = self._abbr_set
        amax = self._abbr_maxlen
        out = []
        i = 0
        n = len(toks)
        while i < n:
            if (toks[i][1] == "word" and i + 1 < n and toks[i + 1][0] == "."
                    and len(toks[i][0]) < amax
                    and (toks[i][0] + ".").lower() in aset):
                out.append((toks[i][0] + ".", "abbr"))
                i += 2
            else:
                out.append(toks[i])
                i += 1
        return out

    def _word(self, w):
        return [(p, "word") for p in _camel_split(w)] if self.split_camel_case else [(w, "word")]

    def tokenize(self, text):
        """Tokenize a paragraph (may contain newlines) into a list of Tokens."""
        flat = []   # (text, type, space_after)
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line[0] == "<" and line[-1] == ">" and _XMLTAG.fullmatch(line):
                flat.append((line, "xmltag", True))
                continue
            for w in line.split():
                subs = self._word(w) if w.isalpha() else self._process(w)
                last = len(subs) - 1
                for j, (t, ty) in enumerate(subs):
                    flat.append((t, ty, j == last))
        tokens = []
        for t, ty, sa in flat:
            if ty == "xmltag":
                tokens.append(Token(t, markup=True,
                                    markup_class="end" if t.startswith("</") else "start",
                                    markup_eos=False, locked=True))
            else:
                tokens.append(Token(t, token_class=_TYPE2CLASS.get(ty, "regular"),
                                    space_after=sa))
        return tokens
