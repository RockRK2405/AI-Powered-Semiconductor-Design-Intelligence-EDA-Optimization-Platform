import io
import tarfile

import numpy as np
import pytest

from siliconai.log_intelligence.diagnose import TemplateClassifier, template_novelty
from siliconai.log_intelligence.e5 import Run, extract_archives, macro_f1, run_e5
from siliconai.log_intelligence.logs import Line
from siliconai.log_intelligence.rules import FAILURE_CLASSES

MSG = {
    "syntax_error": "x.v:{n}: ERROR: syntax error, unexpected TOK_END",
    "elaboration_error": "ERROR: Module `\\m{n}' referenced in `\\t' is not part of the design.",
    "missing_file": "make: *** No rule to make target '/a/b/f{n}.v', needed by 'c'.  Stop.",
    "sdc_error": 'invalid command name "bogus_{n}"',
    "floorplan_capacity": "[ERROR PDN-0185] Insufficient width ({n}.8 um) to add straps",
    "routing_resources": "[ERROR GRT-0232] Routing congestion too high. ({n})",
    "out_of_memory": "make[1]: *** [Makefile:{n}: do-5_2_route] Error 247",
    "timeout": "make[1]: *** [Makefile:{n}: do-4_1_cts] Terminated",
}


def fake_run(i: int, cls: str, group: str, variant: str = "v1") -> Run:
    body = [f"[INFO GPL-0002] Iteration {i * 7} overflow {i % 5}" for _ in range(5)]
    body += [f"Design area {100 + i} um^2 {i % 90}% utilization."]
    if cls != "none":
        body += [MSG[cls].format(n=i), "make: *** [Makefile:1: x] Error 2"]
    lines = [Line("console", k + 1, t) for k, t in enumerate(body)]
    status = "success" if cls == "none" else "failed"
    return Run(f"r{i}", group, "orfs", "nangate45", cls, variant, status, lines)


@pytest.fixture
def corpus():
    runs, i = [], 0
    for gi in range(4):
        for cls in (*FAILURE_CLASSES, "none"):
            for v in ("v1", "v2"):
                runs.append(fake_run(i, cls, f"g{gi}", v))
                i += 1
    return runs


def test_macro_f1_perfect_and_unknown():
    y = np.array(list(FAILURE_CLASSES))
    assert macro_f1(y, y) == 1.0
    assert macro_f1(y, np.array(["unknown"] * len(y))) == 0.0


def test_template_classifier_learns_and_gives_evidence(corpus):
    lab = [r for r in corpus if r.cls != "none"]
    tr = [r for r in lab if r.group != "g0"]
    te = [r for r in lab if r.group == "g0"]
    m = TemplateClassifier().fit([r.lines for r in tr], [r.cls for r in tr])
    n_tpl = len(m.tpl.drain.templates)
    pred = m.predict([r.lines for r in te])
    assert (pred == np.array([r.cls for r in te])).mean() == 1.0
    assert len(m.tpl.drain.templates) == n_tpl  # test runs never add templates
    ev = m.evidence(te[0].lines, pred[0])
    assert ev[0].text == te[0].lines[-2].text  # the planted root-cause line ranks first


def test_template_novelty_flags_unseen_lines(corpus):
    clean = [r.lines for r in corpus if r.cls == "none" and r.group != "g0"]
    test = [r for r in corpus if r.group == "g0"]
    s = template_novelty(clean, [r.lines for r in test])
    failed = np.array([r.cls != "none" for r in test])
    assert s[failed].min() > s[~failed].max()


def test_run_e5_end_to_end(corpus):
    out = run_e5(corpus)
    assert out["n_labelled"] == 4 * 8 * 2 and out["n_clean_success"] == 8
    p1 = out["P1_design_macro_f1_tpl_minus_kw"]
    assert p1["a"] == 1.0 and p1["b"] == 1.0 and p1["n_groups"] == 4
    assert 0.0 <= out["P3_evidence_top3_tpl_minus_errorlines"]["a"] <= 1.0
    assert out["S3a_anomaly_auroc_failed_vs_clean"] == 1.0
    assert set(out["S6_manifestation"]) >= {"timeout/v1", "none/v2"}


def test_extract_archives_blocks_traversal(tmp_path):
    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(bad, "w:gz") as t:
        data = b"x"
        info = tarfile.TarInfo("../escape.log")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    with pytest.raises(tarfile.FilterError):
        extract_archives([bad], tmp_path / "out")
    assert not (tmp_path / "escape.log").exists()
