"""Drain log-template mining (He, Zhu, Zheng, Lyu, ICWS 2017; research/08 R50).

A small, dependency-free implementation of the published algorithm:

1. Mask obvious variables (numbers, hex, paths, quoted strings) with ``<*>``.
2. Route a line through a fixed-depth tree: first by token count, then by its first
   ``depth - 2`` tokens (a token containing a digit or ``<*>`` routes to the ``<*>`` child).
3. In the leaf, pick the template with the highest *sequence similarity* (share of positions
   where the template token equals the line token). At or above ``sim_threshold``, merge:
   differing positions become ``<*>``. Otherwise start a new template.

``fit`` learns templates; ``match`` maps a line to a learned template *without* changing the
tree, so test-fold logs never add templates (no vocabulary leakage across folds).

Logs are untrusted input: lines are truncated to ``max_line_chars`` and tokens to
``max_tokens`` before parsing; nothing is evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WILDCARD = "<*>"
_MASKS = [
    (re.compile(r"(?:/[\w.\-@+]+){2,}/?"), WILDCARD),  # paths
    (re.compile(r"`[^'`]{0,200}'|'[^']{0,200}'|\"[^\"]{0,200}\""), WILDCARD),  # quoted
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), WILDCARD),
    # stand-alone numbers only: message codes (GPL-0301) and units (um^2) are kept
    (re.compile(r"(?<![\w\-^.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?!\w)"), WILDCARD),
]
_HAS_DIGIT = re.compile(r"\d")


def mask(line: str) -> str:
    for rx, rep in _MASKS:
        line = rx.sub(rep, line)
    return line


@dataclass
class Template:
    tid: int
    tokens: list[str]
    count: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.tokens)


@dataclass
class _Node:
    children: dict[str, _Node] = field(default_factory=dict)
    templates: list[Template] = field(default_factory=list)


class Drain:
    def __init__(
        self,
        depth: int = 4,
        sim_threshold: float = 0.5,
        max_children: int = 100,
        max_line_chars: int = 500,
        max_tokens: int = 64,
    ) -> None:
        if depth < 3:
            raise ValueError("depth must be >= 3")
        self.depth = depth
        self.st = sim_threshold
        self.max_children = max_children
        self.max_line_chars = max_line_chars
        self.max_tokens = max_tokens
        self.root = _Node()
        self.templates: list[Template] = []

    # ------------------------------------------------------------------ helpers
    def tokens(self, line: str) -> list[str]:
        return mask(line[: self.max_line_chars]).split()[: self.max_tokens]

    def _leaf(self, toks: list[str], create: bool) -> _Node | None:
        node = self.root.children.get(str(len(toks)))
        if node is None:
            if not create:
                return None
            node = self.root.children[str(len(toks))] = _Node()
        for tok in toks[: self.depth - 2]:
            key = WILDCARD if (_HAS_DIGIT.search(tok) or tok == WILDCARD) else tok
            nxt = node.children.get(key)
            if nxt is None and not create:
                nxt = node.children.get(WILDCARD)
                if nxt is None:
                    return None
            elif nxt is None:
                if len(node.children) >= self.max_children:
                    key = WILDCARD
                nxt = node.children.setdefault(key, _Node())
            node = nxt
        return node

    @staticmethod
    def _sim(tpl: list[str], toks: list[str]) -> tuple[float, int]:
        same = sum(a == b for a, b in zip(tpl, toks, strict=True))
        params = sum(a == WILDCARD for a in tpl)
        return same / max(len(toks), 1), params

    def _best(self, leaf: _Node, toks: list[str]) -> Template | None:
        best, best_key = None, (-1.0, -1)
        for t in leaf.templates:
            key = self._sim(t.tokens, toks)
            if key > best_key:
                best, best_key = t, key
        if best is not None and best_key[0] >= self.st:
            return best
        return None

    # ------------------------------------------------------------------ API
    def add(self, line: str) -> int | None:
        """Learn from one line; returns its template id (None for an empty line)."""
        toks = self.tokens(line)
        if not toks:
            return None
        leaf = self._leaf(toks, create=True)
        if leaf is None:  # cannot happen with create=True
            raise RuntimeError("drain: no leaf")
        t = self._best(leaf, toks)
        if t is None:
            t = Template(len(self.templates), list(toks))
            leaf.templates.append(t)
            self.templates.append(t)
        else:
            t.tokens = [a if a == b else WILDCARD for a, b in zip(t.tokens, toks, strict=True)]
        t.count += 1
        return t.tid

    def fit(self, lines) -> Drain:
        for ln in lines:
            self.add(ln)
        return self

    def match(self, line: str) -> int | None:
        """Template id of ``line`` among learned templates, or None (unseen / empty).

        A learned template matches if every non-wildcard token equals the line's token.
        """
        toks = self.tokens(line)
        if not toks:
            return None
        leaf = self._leaf(toks, create=False)
        if leaf is None:
            return None
        for t in leaf.templates:
            if all(a in (WILDCARD, b) for a, b in zip(t.tokens, toks, strict=True)):
                return t.tid
        return None
