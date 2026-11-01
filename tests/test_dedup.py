from scout.models import Paper
from scout.sources import dedup
from scout.sources.ids import parse_ref


def test_dedup_merges_by_arxiv_and_title():
    a = Paper(id="2501.00001", arxiv_id="2501.00001", title="A Great Paper", source_lanes={"niche"})
    b = Paper(id="s2:abc", s2_id="abc", title="a great paper!", citation_count=10, source_lanes={"field"})
    c = Paper(id="2501.00002", arxiv_id="2501.00002", title="Other")
    out = dedup([a, b, c])
    assert len(out) == 2
    assert out[0].citation_count == 10
    assert out[0].source_lanes == {"niche", "field"}
    assert out[0].id == "2501.00001"


def test_parse_ref():
    assert parse_ref("https://arxiv.org/abs/2501.12345v2") == {"kind": "arxiv", "value": "2501.12345"}
    assert parse_ref("arXiv:2501.12345") == {"kind": "arxiv", "value": "2501.12345"}
    assert parse_ref("https://arxiv.org/pdf/2501.12345.pdf")["value"] == "2501.12345"
    assert parse_ref("https://doi.org/10.1000/xyz123")["kind"] == "doi"
    assert parse_ref("https://openreview.net/forum?id=AbC_12")["value"] == "AbC_12"
