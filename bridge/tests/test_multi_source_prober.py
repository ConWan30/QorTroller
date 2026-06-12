"""HWFL-1 multi_source_prober tests — F-HWFL-5-1 closure verifier."""
from __future__ import annotations

from bridge.vapi_bridge.multi_source_prober import (
    ProbeResult,
    ReachState,
    probe,
)


def _make_fetcher(responses):
    """responses: dict[url, ProbeResult]"""
    def _fetch(url):
        return responses.get(url, ProbeResult(url=url, status=None, error="not in fixture"))
    return _fetch


# ---------------------------------------------------------------------- T1
def test_reachable_2xx():
    f = _make_fetcher({
        "https://example.com": ProbeResult(url="https://example.com", status=200, elapsed_ms=42),
    })
    r = probe(["https://example.com"], "test", f)
    assert r.lines[0].state == ReachState.REACHABLE
    assert r.lines[0].status == 200
    assert "HEAD 200" in r.lines[0].evidence


# ---------------------------------------------------------------------- T2
def test_forbidden_403_is_distinct_from_not_found():
    f = _make_fetcher({
        "https://mc.example/p": ProbeResult(url="https://mc.example/p", status=403),
    })
    r = probe(["https://mc.example/p"], "microchip", f)
    assert r.lines[0].state == ReachState.FORBIDDEN
    assert "anti-bot" in r.lines[0].evidence


# ---------------------------------------------------------------------- T3
def test_not_found_404():
    f = _make_fetcher({"https://wiki.example/none": ProbeResult(url="https://wiki.example/none", status=404)})
    r = probe(["https://wiki.example/none"], "wikipedia", f)
    assert r.lines[0].state == ReachState.NOT_FOUND


# ---------------------------------------------------------------------- T4
def test_timeout_classified_distinctly_from_network_error():
    f = _make_fetcher({
        "https://mouser.example/p": ProbeResult(url="https://mouser.example/p", status=None, error="timeout after 60s"),
        "https://digikey.example/p": ProbeResult(url="https://digikey.example/p", status=None, error="DNS resolution failed"),
    })
    r = probe(["https://mouser.example/p", "https://digikey.example/p"], "vendors", f)
    assert r.lines[0].state == ReachState.TIMEOUT
    assert r.lines[1].state == ReachState.NETWORK_ERROR


# ---------------------------------------------------------------------- T5
def test_redirect_3xx_separate_from_reachable():
    f = _make_fetcher({"https://r.example": ProbeResult(url="https://r.example", status=301)})
    r = probe(["https://r.example"], "redir", f)
    assert r.lines[0].state == ReachState.REDIRECTED
    assert "follow-up" in r.lines[0].evidence


# ---------------------------------------------------------------------- T6
def test_server_error_5xx():
    f = _make_fetcher({"https://s.example": ProbeResult(url="https://s.example", status=503)})
    r = probe(["https://s.example"], "srv", f)
    assert r.lines[0].state == ReachState.SERVER_ERROR


# ---------------------------------------------------------------------- T7
def test_cycle5_failure_pattern_correctly_classified():
    """Reproduces the F-HWFL-5-1 driver scenario: 4/4 fetches all failed
    in Cycle 5 with different failure modes. The prober must classify
    each distinctly so the operator can route around."""
    f = _make_fetcher({
        "https://www.microchip.com/atecc608a": ProbeResult(url="https://www.microchip.com/atecc608a", status=403),
        "https://en.wikipedia.org/wiki/Bogus": ProbeResult(url="https://en.wikipedia.org/wiki/Bogus", status=404),
        "https://www.mouser.com/slow": ProbeResult(url="https://www.mouser.com/slow", status=None, error="timed out after 60s"),
        "https://www.digikey.com/dead": ProbeResult(url="https://www.digikey.com/dead", status=404),
    })
    urls = list(f.__self__.keys()) if hasattr(f, "__self__") else [
        "https://www.microchip.com/atecc608a",
        "https://en.wikipedia.org/wiki/Bogus",
        "https://www.mouser.com/slow",
        "https://www.digikey.com/dead",
    ]
    r = probe(urls, "cycle-5-replay", f)
    states = [ln.state for ln in r.lines]
    assert states == [ReachState.FORBIDDEN, ReachState.NOT_FOUND, ReachState.TIMEOUT, ReachState.NOT_FOUND]


# ---------------------------------------------------------------------- T8
def test_fetcher_returning_none_status_no_error_is_unreachable():
    """Honest fail-open: if fetcher misbehaves and returns nonsense,
    classify as UNREACHABLE rather than crashing or spuriously REACHABLE."""
    f = _make_fetcher({"https://x": ProbeResult(url="https://x", status=None)})
    r = probe(["https://x"], "edge", f)
    assert r.lines[0].state == ReachState.UNREACHABLE


# ---------------------------------------------------------------------- T9
def test_to_markdown_html_pipe_escape_on_url_and_evidence():
    f = _make_fetcher({
        "https://x.com/a|b<script>": ProbeResult(
            url="https://x.com/a|b<script>", status=None,
            error="bad|stuff<>",
        ),
    })
    r = probe(["https://x.com/a|b<script>"], "advers|arial<test>", f)
    md = r.to_markdown()
    # Label escaped
    assert "advers\\|arial&lt;test&gt;" in md
    # URL pipe escaped
    assert "a\\|b" in md
    # Error pipe escaped
    assert "bad\\|stuff" in md
    # No active markup leaked
    assert "<script>" not in md


# ---------------------------------------------------------------------- T10
def test_distribution_summary_counts_all_states():
    f = _make_fetcher({
        "u1": ProbeResult(url="u1", status=200),
        "u2": ProbeResult(url="u2", status=403),
        "u3": ProbeResult(url="u3", status=404),
        "u4": ProbeResult(url="u4", status=None, error="timeout"),
    })
    r = probe(["u1", "u2", "u3", "u4"], "mix", f)
    md = r.to_markdown()
    assert "REACHABLE=1" in md
    assert "FORBIDDEN=1" in md
    assert "NOT-FOUND=1" in md
    assert "TIMEOUT=1" in md
