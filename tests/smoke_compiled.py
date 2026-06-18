"""Wheel smoke test: assert the installed build is mypyc-compiled and works.

Run against an *installed* wheel (e.g. from cibuildwheel's CIBW_TEST_COMMAND).
Fails loudly if a wheel was accidentally shipped as the pure-Python fallback,
which would silently ship the ~1.2x-slower interpreter path to users.
"""

import sys

import somajo

if not somajo.compiled:
    sys.exit(
        "FAIL: installed SoMaJo wheel is running the pure-Python fallback, "
        "not the mypyc-compiled extensions. The compiled build was expected. "
        f"(somajo.compiled={somajo.compiled!r})"
    )

tok = somajo.SoMaJo("de_CMC")
sentences = list(tok.tokenize_text(["Das ist z.B. ein Test."]))
tokens = [t.text for s in sentences for t in s]
expected = ["Das", "ist", "z.", "B.", "ein", "Test", "."]
if tokens != expected:
    sys.exit(f"FAIL: tokenization mismatch: {tokens!r} != {expected!r}")

print(f"OK: compiled wheel, somajo {somajo.__version__}, tokenize sane")
