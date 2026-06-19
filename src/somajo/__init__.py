import importlib.metadata

from . import (
    sentence_splitter,
    somajo,
    tokenizer
)
from ._compiled import PerformanceWarning, is_compiled

__version__ = importlib.metadata.version(__package__ or __name__)

Tokenizer = tokenizer.Tokenizer
SentenceSplitter = sentence_splitter.SentenceSplitter
SoMaJo = somajo.SoMaJo

#: True when the hot tokenizer modules are loaded as mypyc-compiled extensions.
compiled = is_compiled()
