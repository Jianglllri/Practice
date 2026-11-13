"""Regression coverage for the shared interview review queue."""

import json
from datetime import date
from pathlib import Path

import interview_review
import progress
import pytest


def test_grind75_chinese_links_cover_the_upstream_list():
    rows = json.loads(
        (Path(__file__).resolve().parent.parent / "scripts/grind75_table.json").read_text()
    )
    cards = interview_review.load_cards()
    algorithms = {card_id: card for card_id, card in cards.items() if card["kind"] == "algorithm" and not card.get("interview_only")}
    assert len(algorithms) == 75
    assert list(algorithms) == [
        row["slug"].replace("-", "_") for row in rows if row["number"] is not None
    ]
    assert set(algorithms) <= set(progress.discover_problems())
    assert all(card["solution"].endswith("/README.md") for card in algorithms.values())


def test_review_ladder_and_reset():
    record = interview_review.record_review
    first = record(None, "hinted", date(2026, 11, 13), "需要提示")
    assert first["due"] == "2026-11-16"
    with pytest.raises(ValueError, match="early pass"):
        record(first, "passed", date(2026, 11, 15), "")
    second = record(first, "passed", date(2026, 11, 16), "")
    assert second["due"] == "2026-11-26"
    third = record(second, "passed", date(2026, 11, 26), "")
    assert third["due"] == "2026-12-26"
    finished = record(third, "passed", date(2026, 12, 26), "")
    assert finished["due"] is None
    assert len(finished["attempts"]) == 4
    assert finished["attempts"][0]["note"] == "需要提示"
    reset = record(third, "missed", date(2026, 12, 26), "")
    assert reset["stage"] == 0
    assert reset["due"] == "2026-12-29"
    assert record(None, "passed", date(2026, 11, 13), "")["due"] is None


def test_all_card_kinds_share_the_persisted_queue(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(progress, "STATE_FILE", tmp_path / "progress.json")
    parser = progress.build_parser()
    card_ids = ["two_sum", "model:bert", "project:rag-regression", "paper:2611.17167"]
    for card_id in card_ids:
        args = parser.parse_args(["review", card_id, "missed", "--note", "验证"])
        assert args.func(args) == 0
    state = progress.load_state()
    assert set(state["reviews"]) == set(card_ids)
    due = date.fromisoformat(state["reviews"]["two_sum"]["due"])
    capsys.readouterr()
    progress.print_due(state, ["two_sum"], due)
    output = capsys.readouterr().out
    for card_id in card_ids:
        assert output.count(card_id) == 1
    args = parser.parse_args(["show", "paper:2611.17167"])
    assert args.func(args) == 0
    assert "arxiv.org" not in capsys.readouterr().out
    args = parser.parse_args(["show", "paper:2611.17167", "--answer"])
    assert args.func(args) == 0
    assert "https://arxiv.org/abs/2611.17167" in capsys.readouterr().out
