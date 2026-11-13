"""Interview card catalog and 3/10/30-day review rules."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
KINDS = ("algorithm", "model", "project", "paper")
RESULTS = ("missed", "hinted", "passed")
INTERVALS = (3, 10, 30)


def canonical_card_id(card_id: str) -> str:
    prefix, separator, name = card_id.partition(":")
    if prefix != "meituan" or not separator:
        return card_id
    renamed = {
        "longcat": "agent-training",
        "longcat-reading": "agent-training-reading",
        "tokenfd": "fine-grained-text",
        "ava-plan": "workflow-plan",
        "ava-repair": "workflow-repair",
    }
    return "case:" + renamed.get(name, name)


def load_cards() -> dict[str, dict]:
    cards = {}
    for filename in ("grind75_zh.json", "interview_cards.json", "industry_cards.json"):
        entries = json.loads((DIRECTORY / filename).read_text(encoding="utf-8"))
        for entry in entries:
            card_id = entry["id"]
            if card_id in cards:
                raise ValueError(f"duplicate card ID: {card_id}")
            cards[card_id] = {"kind": "algorithm", **entry}
    selected = json.loads((DIRECTORY / "interview_algorithms.json").read_text(encoding="utf-8"))
    for entry in selected:
        card_id = entry["id"]
        cards[card_id] = {**cards.get(card_id, {}), **entry, "kind": "algorithm", "interview": True,
                          "interview_only": card_id not in cards}
    for entry in json.loads((DIRECTORY / "xiaohongshu_cards.json").read_text(encoding="utf-8")):
        card_id = entry["id"]
        if card_id in cards:
            cards[card_id].update(sources=entry["sources"])
        else:
            cards[card_id] = {**entry, "interview_only": entry["kind"] == "algorithm"}
        if "source_followup" in entry:
            cards[card_id]["source_followup"] = entry["source_followup"]
    for entry in json.loads((DIRECTORY / "github_cards.json").read_text(encoding="utf-8")):
        card_id = entry["id"]
        if card_id in cards:
            cards[card_id].setdefault("sources", []).extend(entry["sources"])
            cards[card_id]["github_followup"] = entry["github_followup"]
        else:
            cards[card_id] = entry
    return cards


def record_review(previous: dict | None, result: str, today: date, note: str) -> dict:
    attempts = previous["attempts"] if previous else []
    stage = None
    if result != "passed":
        stage = 0
    elif previous and previous["due"]:
        if today < date.fromisoformat(previous["due"]):
            raise ValueError(f"Review is due on {previous['due']}; an early pass cannot advance it.")
        next_stage = previous["stage"] + 1
        if next_stage < len(INTERVALS):
            stage = next_stage
    due = (today + timedelta(days=INTERVALS[stage])).isoformat() if stage is not None else None
    return {
        "stage": stage,
        "due": due,
        "attempts": [*attempts, {"date": today.isoformat(), "result": result, "note": note}],
    }

def history_version(attempts: list[dict]) -> str:
    return hashlib.sha256(json.dumps(attempts, sort_keys=True).encode()).hexdigest()


def replay_attempts(attempts: list[dict]) -> dict:
    record = None
    for attempt in attempts:
        try:
            record = record_review(
                record, attempt["result"], date.fromisoformat(attempt["date"]), attempt["note"]
            )
        except ValueError:
            # Removing an earlier attempt can make a later pass premature.
            record["attempts"].append(attempt)
    return record
