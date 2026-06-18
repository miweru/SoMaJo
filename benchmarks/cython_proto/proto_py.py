"""Pure-Python reference for the orchestration microbenchmark.

Models the SoMaJo hot path exactly: a doubly-linked list of Token objects, and a
cascade that, for each rule, walks the list and splits each token on the rule's
regex matches. The regex matching itself (the `regex` module) is identical
across all three implementations (pure / mypyc / Cython), so timing differences
isolate the *orchestration* overhead — the loop, attribute access, object
creation and list surgery — which is what native compilation attacks.

This same file is also compiled with mypyc (as proto_mypyc) for the comparison.
"""


class Token:
    def __init__(self, text, token_class="regular", locked=False, space_after=True,
                 original_spelling=None, first_in_sentence=False,
                 last_in_sentence=False, markup=False):
        self.text = text
        self.token_class = token_class
        self.locked = locked
        self.space_after = space_after
        self.original_spelling = original_spelling
        self.first_in_sentence = first_in_sentence
        self.last_in_sentence = last_in_sentence
        self.markup = markup


class DLLElement:
    def __init__(self, value):
        self.value = value
        self.prev = None
        self.next = None


class DLL:
    def __init__(self):
        self.first = None
        self.last = None
        self.size = 0

    def append(self, value):
        el = DLLElement(value)
        el.prev = self.last
        if self.last is not None:
            self.last.next = el
        if self.first is None:
            self.first = el
        self.last = el
        self.size += 1

    def insert_left(self, value, ref):
        el = DLLElement(value)
        el.prev = ref.prev
        el.next = ref
        if ref.prev is not None:
            ref.prev.next = el
        ref.prev = el
        if self.first is ref:
            self.first = el
        self.size += 1

    def remove(self, el):
        if self.first is el:
            self.first = el.next
        if self.last is el:
            self.last = el.prev
        if el.prev is not None:
            el.prev.next = el.next
        if el.next is not None:
            el.next.prev = el.prev
        self.size -= 1

    def texts(self):
        out = []
        cur = self.first
        while cur is not None:
            out.append(cur.value.text)
            cur = cur.next
        return out


def split_on_boundaries(dll, node, boundaries, token_class):
    n = len(boundaries)
    if n == 0:
        return
    prev_end = 0
    text = node.value.text
    for i in range(n):
        start = boundaries[i][0]
        end = boundaries[i][1]
        left = text[prev_end:start]
        match = text[start:end]
        right = text[end:]
        prev_end = end
        left_sa = left.endswith(" ") or match.startswith(" ")
        if match.endswith(" ") or right.startswith(" "):
            match_sa = True
        elif right == "":
            match_sa = node.value.space_after
        else:
            match_sa = False
        left = left.strip()
        match = match.strip()
        right = right.strip()
        if left != "":
            dll.insert_left(Token(left, "regular", False, left_sa), node)
        dll.insert_left(Token(match, token_class, True, match_sa), node)
        if i == n - 1 and right != "":
            dll.insert_left(Token(right, "regular", False, node.value.space_after), node)
    dll.remove(node)


def run_cascade(dll, rules):
    """rules: list of (compiled_regex, token_class, guard_tuple_or_None)."""
    for rx, tc, guard in rules:
        t = dll.first
        while t is not None:
            nxt = t.next
            v = t.value
            if not v.markup and not v.locked:
                text = v.text
                run = True
                if guard is not None:
                    run = False
                    for s in guard:
                        if s in text:
                            run = True
                            break
                if run:
                    boundaries = [(m.start(), m.end()) for m in rx.finditer(text)]
                    if boundaries:
                        split_on_boundaries(dll, t, boundaries, tc)
            t = nxt
    return dll


def build_dll(paragraphs):
    dll = DLL()
    for p in paragraphs:
        dll.append(Token(p, "regular"))
    return dll
