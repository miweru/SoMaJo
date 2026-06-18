# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Cython cdef version of the orchestration microbenchmark — same logic as
proto_py.py, but Token/DLLElement/DLL are cdef classes (C structs with typed
fields) and the hot loops are typed. The regex matching is the identical Python
`regex` module, so the delta vs proto_py / proto_mypyc is pure orchestration.
"""


cdef class Token:
    cdef public str text
    cdef public str token_class
    cdef public bint locked
    cdef public bint space_after
    cdef public object original_spelling
    cdef public bint first_in_sentence
    cdef public bint last_in_sentence
    cdef public bint markup

    def __cinit__(self, str text, str token_class=u"regular", bint locked=False,
                  bint space_after=True, object original_spelling=None,
                  bint first_in_sentence=False, bint last_in_sentence=False,
                  bint markup=False):
        self.text = text
        self.token_class = token_class
        self.locked = locked
        self.space_after = space_after
        self.original_spelling = original_spelling
        self.first_in_sentence = first_in_sentence
        self.last_in_sentence = last_in_sentence
        self.markup = markup


cdef class DLLElement:
    cdef public Token value
    cdef public DLLElement prev
    cdef public DLLElement next

    def __cinit__(self, Token value):
        self.value = value
        self.prev = None
        self.next = None


cdef class DLL:
    cdef public DLLElement first
    cdef public DLLElement last
    cdef public int size

    def __cinit__(self):
        self.first = None
        self.last = None
        self.size = 0

    cdef void append(self, Token value):
        cdef DLLElement el = DLLElement(value)
        el.prev = self.last
        if self.last is not None:
            self.last.next = el
        if self.first is None:
            self.first = el
        self.last = el
        self.size += 1

    cdef void insert_left(self, Token value, DLLElement ref):
        cdef DLLElement el = DLLElement(value)
        el.prev = ref.prev
        el.next = ref
        if ref.prev is not None:
            ref.prev.next = el
        ref.prev = el
        if self.first is ref:
            self.first = el
        self.size += 1

    cdef void remove(self, DLLElement el):
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
        cdef DLLElement cur = self.first
        while cur is not None:
            out.append(cur.value.text)
            cur = cur.next
        return out


cdef void split_on_boundaries(DLL dll, DLLElement node, list boundaries, str token_class):
    cdef int n = len(boundaries)
    if n == 0:
        return
    cdef int prev_end = 0
    cdef int i, start, end
    cdef str text = node.value.text
    cdef str left, match, right
    cdef bint left_sa, match_sa
    for i in range(n):
        start = boundaries[i][0]
        end = boundaries[i][1]
        left = text[prev_end:start]
        match = text[start:end]
        right = text[end:]
        prev_end = end
        left_sa = left.endswith(u" ") or match.startswith(u" ")
        if match.endswith(u" ") or right.startswith(u" "):
            match_sa = True
        elif right == u"":
            match_sa = node.value.space_after
        else:
            match_sa = False
        left = left.strip()
        match = match.strip()
        right = right.strip()
        if left != u"":
            dll.insert_left(Token(left, u"regular", False, left_sa), node)
        dll.insert_left(Token(match, token_class, True, match_sa), node)
        if i == n - 1 and right != u"":
            dll.insert_left(Token(right, u"regular", False, node.value.space_after), node)
    dll.remove(node)


def run_cascade(DLL dll, list rules):
    cdef DLLElement t, nxt
    cdef Token v
    cdef object rx, guard
    cdef str tc, text, s
    cdef bint run
    cdef list boundaries
    for rule in rules:
        rx = rule[0]
        tc = rule[1]
        guard = rule[2]
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
                    if len(boundaries) > 0:
                        split_on_boundaries(dll, t, boundaries, tc)
            t = nxt
    return dll


def build_dll(paragraphs):
    cdef DLL dll = DLL()
    for p in paragraphs:
        dll.append(Token(p, u"regular"))
    return dll
