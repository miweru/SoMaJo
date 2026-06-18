"""Optional mypyc compilation of the hot modules.

All package metadata lives in ``pyproject.toml``; this file only adds compiled
extension modules when explicitly requested, so the default ``pip install``
stays pure Python and maximally portable.

Build the accelerated version (needs ``mypy`` and a C compiler) with::

    SOMAJO_MYPYC=1 pip install --no-build-isolation .
    # or, for in-place development:
    SOMAJO_MYPYC=1 python setup.py build_ext --inplace

``--no-build-isolation`` is required because ``mypy`` is intentionally not in
``[build-system].requires`` (that would pull it into *every* build, including
the pure-Python default). With isolation on, install mypy into the build env
yourself or drop isolation so the local interpreter's mypy is used.

The compiled ``.so`` modules shadow their ``.py`` sources at import time; the
pure-Python sources remain in the wheel as a fallback. ``token.py`` is
deliberately NOT compiled: its Token objects are pickled to worker processes
during parallel tokenization, and mypyc native classes do not round-trip
through pickle. Released wheels are expected to be built with SOMAJO_MYPYC=1 in
CI (e.g. cibuildwheel); the sdist install path stays pure Python.
"""

import os

from setuptools import setup

ext_modules = []
if os.environ.get("SOMAJO_MYPYC") == "1":
    try:
        from mypyc.build import mypycify
    except ImportError as exc:  # mypy missing from the (isolated) build env
        raise SystemExit(
            "SOMAJO_MYPYC=1 requested a compiled build, but mypy is not "
            "importable in this build environment. Install mypy and rebuild "
            "with `--no-build-isolation`, e.g.:\n"
            "    pip install mypy\n"
            "    SOMAJO_MYPYC=1 pip install --no-build-isolation .\n"
            f"(original error: {exc})"
        )
    ext_modules = mypycify([
        "--ignore-missing-imports",
        "src/somajo/tokenizer.py",
        "src/somajo/doubly_linked_list.py",
        "src/somajo/sentence_splitter.py",
        "src/somajo/alignment.py",
    ])

setup(ext_modules=ext_modules)
