#!/usr/bin/env python3


# Attribute order matches Token.__init__'s assignments; used by the fast
# pickling path below.
_TOKEN_ATTRS = ("text", "markup", "markup_class", "markup_eos", "_locked",
                "token_class", "space_after", "original_spelling",
                "first_in_sentence", "last_in_sentence", "character_offset")


def _remake_token(state):
    """Reconstruct a Token from a positional state tuple, bypassing __init__
    validation (the object was already validated when first created). This is
    the unpickle half of Token.__reduce__ — it rebuilds ~400k tokens in the
    MAIN process when collecting results from parallel workers, so it is kept
    as cheap as possible (a single __dict__ update, no per-attribute setattr)."""
    tok = object.__new__(Token)
    tok.__dict__.update(zip(_TOKEN_ATTRS, state))
    return tok


class Token:
    """Token objects store a piece of text (in the end a single token) with additional information.

    Parameters
    ----------
    text : str
        The text that makes up the token object
    markup : bool, (default=False)
        Is the token a markup token?
    markup_class : {'start', 'end'}, optional (default=None)
        If `markup=True`, then `markup_class` must be either "start" or "end".
    markup_eos : bool, optional (default=None)
        Is the markup token a sentence boundary?
    locked : bool, (default=False)
        Mark the token as locked.
    token_class : {'URL', 'XML_entity', 'XML_tag', 'abbreviation', 'action_word', 'amount', 'date', 'email_address', 'emoticon', 'hashtag', 'measurement', 'mention', 'number', 'ordinal', 'regular', 'semester', 'symbol', 'time'}, optional (default=None)
        The class of the token, e.g. "regular", "emoticon", "URL", etc.
    space_after : bool, (default=True)
        Was there a space after the token in the original data?
    original_spelling : str, optional (default=None)
        The original spelling of the token, if it is different from the one in `text`.
    first_in_sentence : bool, (default=False)
        Is it the first token of a sentence?
    last_in_sentence : bool, (default=False)
        Is it the last token of a sentence?
    character_offset : tuple, (default=None)
        Character offset of the token in the input as tuple `(start, end)`
        such that `input[start:end] == text` (if there are no changes to
        the token text during tokenization)

    """

    token_classes = {
        "URL",
        "XML_entity",
        "XML_tag",
        "abbreviation",
        "action_word",
        "amount",
        "date",
        "email_address",
        "emoticon",
        "hashtag",
        "measurement",
        "mention",
        "number",
        "ordinal",
        "regular",
        "semester",
        "symbol",
        "time",
    }

    def __init__(
            self,
            text,
            *,
            markup=False,
            markup_class=None,
            markup_eos=None,
            locked=False,
            token_class=None,
            space_after=True,
            original_spelling=None,
            first_in_sentence=False,
            last_in_sentence=False,
            character_offset=None
    ):
        self.text = text
        if markup:
            assert markup_class is not None, "You need to specify a `markup_class` for markup tokens."
            assert markup_eos is not None, "You need to provide a value for `markup_eos` for markup tokens."
        if markup_class is not None:
            assert markup, "You can only specify a `markup_class` for markup tokens."
            assert markup_class == "start" or markup_class == "end", f"'{markup_class}' is not a recognized markup class."
        if markup_eos is not None:
            assert markup, "You can only use `markup_eos` for markup tokens."
            assert isinstance(markup_eos, bool), f"'{markup_eos}' is not a Boolean value."
        if token_class is not None:
            assert token_class in self.token_classes, f"'{token_class}' is not a recognized token class."
        self.markup = markup
        self.markup_class = markup_class
        self.markup_eos = markup_eos
        self._locked = locked
        self.token_class = token_class
        self.space_after = space_after
        self.original_spelling = original_spelling
        self.first_in_sentence = first_in_sentence
        self.last_in_sentence = last_in_sentence
        self.character_offset = character_offset

    def __reduce__(self):
        # Pickle as a compact positional tuple instead of the default __dict__
        # pickle. On the parallel path this roughly halves the IPC blob and
        # makes the serial main-process unpickle (the multicore bottleneck)
        # ~25 % cheaper; reconstruction goes through _remake_token. Output is
        # identical — the same Token objects are rebuilt. token.py stays pure
        # Python (mypyc native classes don't round-trip through pickle).
        d = self.__dict__
        return (_remake_token, (tuple(d[a] for a in _TOKEN_ATTRS),))

    def __str__(self):
        return self.text

    @property
    def extra_info(self) -> str:
        """String representation of extra information.

        Returns
        -------
        str
            A string representation of the `space_after` and `original_spelling` attributes.

        Examples
        --------
        >>> tok = Token(":)", token_class="regular", space_after=False, original_spelling=": )")
        >>> print(tok.text)
        :)
        >>> print(tok.extra_info)
        SpaceAfter=No, OriginalSpelling=": )"

        """
        info = []
        if not self.space_after:
            info.append("SpaceAfter=No")
        if self.original_spelling is not None:
            info.append("OriginalSpelling=\"%s\"" % self.original_spelling)
        return ", ".join(info)
