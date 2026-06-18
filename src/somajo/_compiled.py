"""Detect whether the hot modules run as mypyc-compiled extensions.

The compiled ``.so``/``.pyd`` modules shadow their ``.py`` sources at import
time, so the cheapest reliable probe is the suffix of the imported module's
``__file__``. When SoMaJo runs the pure-Python fallback we emit a single
``PerformanceWarning`` pointing at the build command; set
``SOMAJO_NO_COMPILE_WARNING=1`` (or filter the category) to silence it.
"""

import os
import warnings


class PerformanceWarning(UserWarning):
    """Issued once when SoMaJo runs interpreted instead of mypyc-compiled."""


def is_compiled():
    """Return True when the tokenizer is imported from a compiled extension."""
    from . import tokenizer
    return tokenizer.__file__.endswith((".so", ".pyd"))


_warned = False


def warn_if_interpreted(stacklevel=3):
    """Emit a one-time PerformanceWarning when running the pure-Python build.

    No-op when the modules are compiled, when SOMAJO_NO_COMPILE_WARNING is set,
    or after the first call (so constructing many SoMaJo objects warns once).
    """
    global _warned
    if _warned or os.environ.get("SOMAJO_NO_COMPILE_WARNING") or is_compiled():
        return
    _warned = True
    warnings.warn(
        "SoMaJo is running the pure-Python modules; the mypyc-compiled build "
        "is ~1.2x faster on a single core. Build it with "
        "`SOMAJO_MYPYC=1 pip install --force-reinstall --no-build-isolation .` "
        "(needs a C compiler and mypy). Set SOMAJO_NO_COMPILE_WARNING=1 to "
        "silence this hint.",
        category=PerformanceWarning,
        stacklevel=stacklevel,
    )
