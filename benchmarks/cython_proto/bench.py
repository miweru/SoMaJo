"""3-way orchestration microbenchmark: pure Python vs mypyc vs Cython cdef.

Same workload (real EmpiriST text + ~40 real SoMaJo regexes with their guards),
same `regex` matching — only the Token/DLL/cascade orchestration differs. All
three must produce identical output; the time ratios isolate what native
compilation buys on the orchestration (the ~63% bottleneck).
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import somajo
from benchmarks import corpora

import proto_py
import proto_mypyc   # mypyc-compiled copy of proto_py
import proto         # Cython

# A representative slice of the real cascade: plain _split_all_matches rules.
RULE_NAMES = [
    "single_tokens", "mention", "email", "entity", "simple_url",
    "url_without_protocol", "reddit_links", "markdown_links", "heart_emoticon",
    "emoticon", "symbols_and_dingbats", "action_word", "underline",
    "gender_marker", "token_with_plus_ampersand", "isbn", "three_part_date_dmy",
    "three_part_date_mdy", "two_part_date", "time", "ordinal", "number_range",
    "fraction", "calculation", "amount", "semester", "number", "ipv4",
    "section_number", "measurement", "quest_exclam", "arrow", "all_parens",
    "de_slash", "letter_apostrophe_word", "paired_single_quot_mark",
    "other_punctuation", "ellipsis", "dot_without_space", "dot",
]


def build_rules():
    T = somajo.SoMaJo("de_CMC")._tokenizer
    rules = []
    for nm in RULE_NAMES:
        rx = getattr(T, nm)
        rules.append((rx, "symbol", T._guards.get(rx)))
    return rules


def bench(mod, paras, rules, runs=5):
    best = float("inf")
    out = None
    for _ in range(runs):
        dll = mod.build_dll(paras)
        t0 = time.perf_counter()
        mod.run_cascade(dll, rules)
        best = min(best, time.perf_counter() - t0)
        out = dll.texts()
    return best, out


def main():
    rules = build_rules()
    paras = (corpora.load_empirist("web", n=4000, seed=1)
             + corpora.load_empirist("cmc", n=4000, seed=1))
    chars = sum(len(p) for p in paras)
    print(f"workload: {len(paras)} paragraphs, {chars} chars, {len(rules)} rules\n")

    res = {}
    for name, mod in [("pure", proto_py), ("mypyc", proto_mypyc), ("cython", proto)]:
        res[name] = bench(mod, paras, rules)

    outs = {k: v[1] for k, v in res.items()}
    identical = outs["pure"] == outs["mypyc"] == outs["cython"]
    print(f"identical output across all 3: {identical}  ({len(outs['pure'])} tokens)\n")
    for k in ("pure", "mypyc", "cython"):
        print(f"  {k:8} {res[k][0]:.3f}s")
    print()
    print(f"  mypyc  vs pure  : {res['pure'][0] / res['mypyc'][0]:.2f}x")
    print(f"  cython vs pure  : {res['pure'][0] / res['cython'][0]:.2f}x")
    print(f"  >>> cython vs mypyc (the real question): "
          f"{res['mypyc'][0] / res['cython'][0]:.2f}x")


if __name__ == "__main__":
    main()
