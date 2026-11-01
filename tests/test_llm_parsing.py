from scout.llm.base import _json_list, _json_obj


def test_json_list_tolerates_prose():
    assert _json_list('Sure: ["a b", "c d"]') == ["a b", "c d"]
    assert _json_list("- one\n- two") == ["one", "two"]


def test_json_obj():
    assert _json_obj('```json\n{"why": "x", "payoff": "y"}\n```')["payoff"] == "y"
    assert _json_obj("nope") == {}
