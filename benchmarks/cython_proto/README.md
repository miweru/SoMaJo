# Cython cdef prototype — evaluated, NOT pursued

A 3-way microbenchmark answering the question: *can hand-written Cython `cdef`
beat the already-shipped mypyc build on the cascade orchestration (the ~63%
bottleneck), while keeping the `regex` module so output stays byte-identical?*

It models the SoMaJo hot path exactly — a doubly-linked list of `Token`s and a
cascade that walks the list per rule and splits each token on its regex matches
— in three implementations with identical logic and identical `regex` matching:

- `proto_py.py` — pure Python
- `proto_mypyc` — `proto_py.py` compiled with mypyc (built in a flat dir to
  avoid the package-path issue: `cp proto_py.py /tmp/mpc/proto_mypyc.py && (cd /tmp/mpc && mypyc proto_mypyc.py)`)
- `proto.pyx` — Cython, with `Token`/`DLLElement`/`DLL` as `cdef` classes and
  typed hot loops (`cythonize -i proto.pyx`)

Run: `PYTHONPATH=/tmp/mpc python bench.py` (from repo root).

## Result (real EmpiriST text, ~40 real SoMaJo rules)

| workload | pure | mypyc | cython | cython/mypyc |
|---|---|---|---|---|
| pure loop + dispatch (no-match rules) | 0.103 | 0.084 | 0.074 | **1.14×** |
| string-slice + object creation (match-heavy) | 0.399 | 0.345 | 0.296 | **1.16×** |
| full (matching included) | 0.529 | 0.493 | 0.461 | **1.07×** |

All three produce **identical output**.

## Conclusion: not worth it

Cython gives only **~1.1× over the mypyc build we already ship** (≈1.07× on the
full workload, diluted by the identical regex-matching cost). The hypothesis of
1.3–1.8× was wrong, for two reasons:

1. **mypyc already compiles the loop/object/DLL part well** — hand-written
   `cdef` typing is only ~15% tighter on that part.
2. **The string operations dominate and stay Python-level in both** — `text[start:end]`
   slicing, `.strip()`, `.endswith()`, and the `regex` `finditer` + match-object
   iteration are identical across pure / mypyc / Cython. Only a span-based model
   (indices instead of substring copies, materialized once at the end) could
   touch that — and that is the separate, high-effort, ~1.1× span redesign.

So the profiled "~63% orchestration" is mostly **inherent string/regex work**,
not raw interpreter loop overhead — which is why neither mypyc nor Cython can
crush it. A full Cython rewrite of the core would buy ~7–15% over today's build
for a multi-week, dual-build-system effort. Prototyping first (this) avoided
that rewrite.
