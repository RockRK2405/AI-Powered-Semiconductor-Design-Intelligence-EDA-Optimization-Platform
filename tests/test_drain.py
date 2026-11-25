from siliconai.log_intelligence.drain import WILDCARD, Drain, mask


def test_mask_numbers_paths_quotes():
    assert mask("[ERROR GPL-0301] Utilization 109.246 % exceeds 100%.") == (
        "[ERROR GPL-0301] Utilization <*> % exceeds <*>."
    )
    assert mask("cannot open /a/b/c.v now") == "cannot open <*> now"
    assert mask('invalid command name "foo_bar"') == "invalid command name <*>"
    assert mask("Module `\\x' not found") == "Module <*> not found"


def test_merges_lines_differing_in_variables():
    d = Drain().fit(
        [
            "[INFO GRT-0101] Running extra iterations to remove overflow.",
            "Design area 2855 um^2 77% utilization.",
            "Design area 3572 um^2 97% utilization.",
            "Inserted 48 tapcells into row core",
            "Inserted 52 tapcells into row io",
        ]
    )
    texts = {t.text for t in d.templates}
    assert "Design area <*> um^2 <*> utilization." in texts
    assert f"Inserted <*> tapcells into row {WILDCARD}" in texts
    assert len(d.templates) == 3


def test_match_does_not_learn():
    d = Drain().fit(["Design area 10 um^2 5% utilization."])
    n = len(d.templates)
    assert d.match("Design area 99 um^2 50% utilization.") == 0
    assert d.match("Something never seen before here") is None
    assert len(d.templates) == n


def test_untrusted_lines_are_bounded():
    d = Drain(max_line_chars=50, max_tokens=5)
    tid = d.add("x " * 10_000)
    assert tid == 0 and len(d.templates[0].tokens) == 5
    assert d.add("") is None and d.match("   ") is None


def test_deterministic():
    lines = [f"step {i} took {i * 3} s on core {i % 4}" for i in range(50)] + ["done"]
    a = [t.text for t in Drain().fit(lines).templates]
    b = [t.text for t in Drain().fit(lines).templates]
    assert a == b
