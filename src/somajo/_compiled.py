"""Detect whether the hot modules run as mypyc-compiled extensions.

The compiled ``.so``/``.pyd`` modules shadow their ``.py`` sources at import
time, so the cheapest reliable probe is the suffix of the imported module's
``__file__``. When SoMaJo runs the pure-Python fallback we emit a single
``PerformanceWarning`` pointing at the build command; set
``SOMAJO_NO_COMPILE_WARNING=1`` (or filter the category) to silence it.
"""

import multiprocessing
import os
import warnings


class PerformanceWarning(UserWarning):
    """Issued once when SoMaJo runs interpreted instead of mypyc-compiled."""


def is_compiled():
    """Return True when the tokenizer is imported from a compiled extension."""
    from . import tokenizer
    # __file__ can be None/absent under frozen or embedded interpreters; treat
    # that as "not compiled" rather than raising out of `import somajo`.
    path = getattr(tokenizer, "__file__", None) or ""
    return path.endswith((".so", ".pyd"))


_warned = False


def warn_if_interpreted(stacklevel=3):
    """Emit a one-time PerformanceWarning when running the pure-Python build.

    No-op when the modules are compiled, when SOMAJO_NO_COMPILE_WARNING is set,
    after the first call in a process, or inside a multiprocessing worker (the
    main process already warns, so the pool would otherwise emit one duplicate
    per worker, each pointing at an unhelpful internal frame).
    """
    global _warned
    if _warned or os.environ.get("SOMAJO_NO_COMPILE_WARNING") or is_compiled():
        return
    if multiprocessing.parent_process() is not None:
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
