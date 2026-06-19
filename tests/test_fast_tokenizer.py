#!/usr/bin/env python3

import copy
import pickle
import time
import unittest

from somajo import SoMaJo
from somajo.fast_tokenizer import FastTokenizer
from somajo.token import Token, _TOKEN_ATTRS, _remake_token


class TestFastTokenizer(unittest.TestCase):
    def setUp(self):
        self.ft = FastTokenizer(language="de_CMC", split_camel_case=True)

    def _texts(self, s):
        return [t.text for t in self.ft.tokenize(s)]

    # --- robustness: must never crash on degenerate input -------------------
    def test_edge_inputs_do_not_crash(self):
        for s in ["", " ", "\n", "\n\n", "   \n  ", "<", ">", "<>", "<foo",
                  "foo>", "<<>>", "a < b > c", "x" * 5000, "\t", "<?xml?>"]:
            self.assertIsInstance(self.ft.tokenize(s), list)

    def test_empty_and_whitespace_yield_no_tokens(self):
        for s in ["", "   ", "\n", "\n\n", " \t \n "]:
            self.assertEqual(self.ft.tokenize(s), [])

    def test_no_redos_on_long_dotted_slashed_tokens(self):
        # an unbounded url2/email prefix backtracks quadratically here; the
        # length-bounded patterns keep it linear. Generous budget = regression
        # guard, not a micro-benchmark.
        for s in ["a/." * 4000, "ab." * 4000, "a.-" * 3000, "a." * 8000 + "@"]:
            t0 = time.perf_counter()
            self.ft.tokenize(s)
            self.assertLess(time.perf_counter() - t0, 2.0,
                            f"tokenize is super-linear on {s[:12]!r}… (ReDoS)")

    # --- the boundary fixes that close the F1 gap to the exact tokenizer -----
    def test_space_emoticon_is_rejoined(self):
        self.assertEqual(self._texts("hey : ) du"), ["hey", ":)", "du"])
        self.assertEqual(self._texts("na ; ( ja"), ["na", ";(", "ja"])

    def test_space_emoticon_phone_exclusion(self):
        # ": ) 0049" / ": ) +49" are phone numbers, not emoticons — the eye and
        # mouth must stay separate (no ":)" merge), mirroring the exact rule.
        for s in ["Tel : ) 0049", "Tel : ) +49", "X ; ( 0099"]:
            merged = {":)", ":(", ";)", ";("} & set(self._texts(s))
            self.assertFalse(merged, f"phone after emoticon wrongly merged in {s!r}")

    def test_url_with_file_extension_is_one_token(self):
        self.assertEqual(self._texts("Icons/security-medium.png"),
                         ["Icons/security-medium.png"])
        self.assertEqual(self._texts("security/verschlüsselung.txt"),
                         ["security/verschlüsselung.txt"])

    # --- inline markup must stay a markup token, not become regular ----------
    def test_inline_xml_tag_is_markup(self):
        toks = self.ft.tokenize("x<b>y")
        tag = [t for t in toks if t.text == "<b>"][0]
        self.assertTrue(tag.markup)
        self.assertEqual(tag.markup_class, "start")

    def test_token_class_and_space_after(self):
        toks = self.ft.tokenize("z.B. das.")
        self.assertEqual([(t.text, t.token_class) for t in toks],
                         [("z.", "abbreviation"), ("B.", "abbreviation"),
                          ("das", "regular"), (".", "symbol")])
        self.assertFalse(toks[0].space_after)   # z. — no space before B.
        self.assertTrue(toks[1].space_after)    # B. — space before das


class TestFastModeAPI(unittest.TestCase):
    def test_fast_sentence_splitting(self):
        tok = SoMaJo("de_CMC", fast=True, split_sentences=True)
        sents = list(tok.tokenize_text(["Was geht?! Alles gut."]))
        self.assertEqual(len(sents), 2)

    def test_fast_rejects_character_offsets(self):
        # ValueError (not assert) so it still raises under `python -O`.
        with self.assertRaises(ValueError):
            SoMaJo("de_CMC", fast=True, character_offsets=True)

    def test_fast_parallel_matches_serial(self):
        paras = ["Heyi : ) z.B. test."] * 5
        tok = SoMaJo("de_CMC", fast=True, split_sentences=True)
        serial = [[t.text for t in s] for s in tok.tokenize_text(paras, parallel=1)]
        par = [[t.text for t in s] for s in tok.tokenize_text(paras, parallel=2)]
        self.assertEqual(serial, par)


class TestTokenPickling(unittest.TestCase):
    """Token.__reduce__ must round-trip every field and stay coupled to
    Token.__init__'s attributes."""

    def test_token_attrs_match_init(self):
        t = Token("x", token_class="regular")
        self.assertEqual(set(t.__dict__.keys()), set(_TOKEN_ATTRS),
                         "_TOKEN_ATTRS is out of sync with Token.__init__")

    def test_pickle_roundtrip_preserves_all_fields(self):
        cases = [
            Token("Haus", token_class="regular", space_after=False),
            Token(":)", token_class="emoticon", original_spelling=": )"),
            Token("<b>", markup=True, markup_class="start", markup_eos=False,
                  locked=True),
            Token("x", token_class="regular", character_offset=(3, 4),
                  first_in_sentence=True, last_in_sentence=True),
        ]
        for t in cases:
            back = pickle.loads(pickle.dumps(t, protocol=pickle.HIGHEST_PROTOCOL))
            self.assertEqual(t.__dict__, back.__dict__)

    def test_copy_and_deepcopy(self):
        t = Token("x", token_class="regular", character_offset=(0, 1))
        self.assertEqual(copy.copy(t).__dict__, t.__dict__)
        self.assertEqual(copy.deepcopy(t).__dict__, t.__dict__)

    def test_remake_token_direct(self):
        t = Token("y", token_class="number", space_after=False)
        again = _remake_token(tuple(t.__dict__[a] for a in _TOKEN_ATTRS))
        self.assertEqual(again.__dict__, t.__dict__)


if __name__ == "__main__":
    unittest.main()
