"""Log-diagnosis models for E5 (docs/experiments.md §11).

- ``TemplateClassifier`` (M-tpl): Drain templates fitted on the training runs only, a run as a
  template-count vector, TF-IDF, logistic regression. Its evidence for a run is the run's lines
  ranked by the coefficient of their template for the predicted class.
- ``RawTextClassifier`` (M-raw): TF-IDF of masked word uni/bigrams, logistic regression.
- ``TemplateSVM`` (M-svc): M-tpl's features with a linear SVM.
- ``template_novelty``: share of a run's lines whose template never occurs in clean runs.

All hyperparameters are fixed by the protocol; nothing is tuned on D2.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfTransformer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from siliconai.log_intelligence.drain import Drain, mask
from siliconai.log_intelligence.logs import Line

SEED = 0
DRAIN_DEPTH, DRAIN_SIM = 4, 0.5


class _Templates:
    """Drain fitted on training runs; maps runs to template-count rows (cached per line text)."""

    def __init__(self, runs: Sequence[Sequence[Line]]) -> None:
        self.drain = Drain(depth=DRAIN_DEPTH, sim_threshold=DRAIN_SIM)
        for run in runs:
            for ln in run:
                self.drain.add(ln.text)
        self._cache: dict[str, int | None] = {}

    @property
    def n(self) -> int:
        return len(self.drain.templates)

    def tid(self, text: str) -> int | None:
        if text not in self._cache:
            self._cache[text] = self.drain.match(text)
        return self._cache[text]

    def counts(self, runs: Sequence[Sequence[Line]]) -> sparse.csr_matrix:
        rows, cols, vals = [], [], []
        for i, run in enumerate(runs):
            c: dict[int, int] = {}
            for ln in run:
                t = self.tid(ln.text)
                if t is not None:
                    c[t] = c.get(t, 0) + 1
            rows += [i] * len(c)
            cols += list(c)
            vals += list(c.values())
        return sparse.csr_matrix((vals, (rows, cols)), shape=(len(runs), self.n), dtype=float)


class TemplateClassifier:
    def __init__(self, svm: bool = False) -> None:
        self.svm = svm

    def fit(self, runs: Sequence[Sequence[Line]], y: Sequence[str]) -> TemplateClassifier:
        self.tpl = _Templates(runs)
        self.tfidf = TfidfTransformer(sublinear_tf=True, smooth_idf=True)
        x = self.tfidf.fit_transform(self.tpl.counts(runs))
        if self.svm:
            self.model = LinearSVC(C=1.0, class_weight="balanced", random_state=SEED)
        else:
            self.model = LogisticRegression(
                C=1.0, class_weight="balanced", max_iter=2000, random_state=SEED
            )
        self.model.fit(x, np.asarray(y))
        return self

    def _x(self, runs: Sequence[Sequence[Line]]):
        return self.tfidf.transform(self.tpl.counts(runs))

    def predict(self, runs: Sequence[Sequence[Line]]) -> np.ndarray:
        return self.model.predict(self._x(runs))

    def predict_proba(self, runs: Sequence[Sequence[Line]]) -> np.ndarray:
        return self.model.predict_proba(self._x(runs))

    @property
    def classes_(self) -> np.ndarray:
        return self.model.classes_

    def _coef_row(self, cls: str) -> np.ndarray:
        coef = self.model.coef_
        if coef.shape[0] == 1:  # binary: sklearn keeps one row for classes_[1]
            return coef[0] if cls == self.classes_[1] else -coef[0]
        return coef[list(self.classes_).index(cls)]

    def evidence(self, run: Sequence[Line], cls: str, k: int = 3) -> list[Line]:
        """Lines ranked by their template's coefficient for ``cls``; later line first on ties;
        distinct texts; lines without a learned template are never evidence."""
        w = self._coef_row(cls)
        scored = []
        for pos, ln in enumerate(run):
            t = self.tpl.tid(ln.text)
            if t is not None:
                scored.append((w[t], pos, ln))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        out, seen = [], set()
        for _, _, ln in scored:
            if ln.text.strip() not in seen:
                out.append(ln)
                seen.add(ln.text.strip())
                if len(out) == k:
                    break
        return out


def _doc(run: Sequence[Line]) -> str:
    return "\n".join(mask(ln.text) for ln in run)


class RawTextClassifier:
    def fit(self, runs: Sequence[Sequence[Line]], y: Sequence[str]) -> RawTextClassifier:
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
        x = self.vec.fit_transform([_doc(r) for r in runs])
        self.model = LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=2000, random_state=SEED
        ).fit(x, np.asarray(y))
        return self

    def predict(self, runs: Sequence[Sequence[Line]]) -> np.ndarray:
        return self.model.predict(self.vec.transform([_doc(r) for r in runs]))


def template_novelty(clean_runs: Sequence[Sequence[Line]], runs: Sequence[Sequence[Line]]):
    """Per run: share of its lines whose template does not occur in ``clean_runs``."""
    tpl = _Templates(clean_runs)
    out = []
    for run in runs:
        n = sum(1 for ln in run if ln.text.strip())
        unseen = sum(1 for ln in run if ln.text.strip() and tpl.tid(ln.text) is None)
        out.append(unseen / n if n else 1.0)
    return np.asarray(out)
