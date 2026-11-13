"""Personal progress tracker for the grind75 practice harness.

Tracks three things the test suite alone cannot: which problems you have
solved, how confident each solve felt, and which problems are due for a
spaced-repetition review. State lives in `.progress.json` next to this file;
it is personal (gitignored) and never read by the tests.

    uv run python progress.py scan                    # run the suite, record per-problem status
    uv run python progress.py rate two_sum shaky      # record a confidence rating
    uv run python progress.py status                  # full board in canonical study order
    uv run python progress.py due                     # just the review queue

Problems live in bank subdirectories (`leetcode/<slug>/`, `amazon/<slug>/`);
the slug is the directory name inside the bank. The layout is discovered at
runtime: bank subdirectories when present, the flat `practice/<slug>/`
layout otherwise, so the tool works across the reorganization transition.

Status semantics: `scan` reports the tests honestly. A problem is `solved`
only while every one of its tests passes, `attempted` when any test fails or
only some pass, and `unsolved` when everything skips (the stub still raises
`NotSolved`). A previously solved problem whose solution reverts to the stub
drops back to `unsolved`, but its history (`solved_date`, confidence rating)
is preserved and keeps driving the review queue. `solved_date` is recorded the
first time a problem becomes solved and is never overwritten.

Review intervals by confidence: struggled = 2 days, shaky = 7, solid = 21,
solved-but-unrated = 14. A problem is due when today >= last_practiced +
interval, where last_practiced is the latest of `solved_date` and the rating
date.
"""

from __future__ import annotations

import argparse
import difflib
import fcntl
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import interview_review

PRACTICE_DIR = Path(__file__).resolve().parent
STATE_FILE = PRACTICE_DIR / ".progress.json"
DOCS_INDEX = PRACTICE_DIR.parent / "docs" / "leetcode" / "index.md"

STATUS_SOLVED = "solved"
STATUS_ATTEMPTED = "attempted"
STATUS_UNSOLVED = "unsolved"

# Spaced-repetition review intervals, in days, keyed by confidence rating.
REVIEW_INTERVALS = {"struggled": 2, "shaky": 7, "solid": 21}
UNRATED_SOLVED_INTERVAL = 14
CONFIDENCE_LEVELS = tuple(sorted(REVIEW_INTERVALS, key=REVIEW_INTERVALS.get))


def discover_problems() -> list[str]:
    """Return every problem slug: a directory holding a solution.py.

    Bank-shaped layout first (`practice/<bank>/<slug>/solution.py` for the
    known banks, leetcode and amazon); when no bank directory exists, the
    flat layout (`practice/<slug>/solution.py`) is discovered instead, so
    both the pre-move and post-move trees work.
    """
    slugs = {
        entry.name
        for bank in ("leetcode", "amazon")
        for entry in _bank_problem_dirs(bank)
    }
    if not slugs:
        slugs = {
            entry.name
            for entry in PRACTICE_DIR.iterdir()
            if entry.is_dir() and (entry / "solution.py").is_file()
        }
    return sorted(slugs)


def _bank_problem_dirs(bank: str) -> list[Path]:
    """Return the problem directories inside one bank holding a solution.py.

    Args:
        bank: The bank directory name under practice/ (leetcode or amazon).

    Returns:
        The bank's problem directories, in name order; empty when the bank
        directory itself does not exist.
    """
    bank_dir = PRACTICE_DIR / bank
    if not bank_dir.is_dir():
        return []
    return sorted(
        entry
        for entry in bank_dir.iterdir()
        if entry.is_dir() and (entry / "solution.py").is_file()
    )


def load_state() -> dict:
    """Load .progress.json, starting fresh (with a warning) if missing or corrupt."""
    if not STATE_FILE.exists():
        return {"schema": 1, "problems": {}}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("problems"), dict):
            raise ValueError("unexpected top-level structure")
        reviews = state.get("reviews", {})
        for card_id in list(reviews):
            canonical_id = interview_review.canonical_card_id(card_id)
            if canonical_id == card_id:
                continue
            previous = reviews.pop(card_id)
            if canonical_id in reviews:
                attempts = sorted(previous["attempts"] + reviews[canonical_id]["attempts"],
                                  key=lambda attempt: attempt["date"])
                previous = interview_review.replay_attempts(attempts)
            reviews[canonical_id] = previous
        return state
    except (ValueError, OSError) as exc:
        print(
            f"warning: could not read {STATE_FILE.name} ({exc}); starting fresh. "
            "Previous history will be overwritten on the next write.",
            file=sys.stderr,
        )
        return {"schema": 1, "problems": {}}


def save_state(state: dict) -> None:
    """Write the state file atomically enough for a single-user tool."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=STATE_FILE.parent, delete=False
    ) as output:
        temporary_path = Path(output.name)
        try:
            json.dump(state, output, indent=2, sort_keys=True)
            output.write("\n")
            output.close()
            temporary_path.replace(STATE_FILE)
        finally:
            temporary_path.unlink(missing_ok=True)


def canonical_order(problems: list[str]) -> list[str]:
    """Return problems in canonical study order.

    Parses the problem table in docs/leetcode/index.md, whose rows the
    index-tables generator emits in the interleaved study order. Amazon
    rows live in the amazon bank's own index and never appear in this
    table, so they sort alphabetically after the tabled problems. Any
    problem missing from the table is appended alphabetically. Falls back
    to alphabetical order if the table cannot be read or has no rows.
    """
    known = set(problems)
    landing = DOCS_INDEX
    row = re.compile(r"^\|\s*\[[^\]]+\]\((?:problems/)?([A-Za-z0-9_]+)\.md\)")
    ordered_rows: list[str] = []
    try:
        for line in landing.read_text(encoding="utf-8").splitlines():
            match = row.match(line)
            if match is not None:
                ordered_rows.append(match.group(1))
    except OSError as exc:
        print(
            f"warning: could not read {landing} ({exc}); listing alphabetically.",
            file=sys.stderr,
        )
        return sorted(problems)
    if not ordered_rows:
        print(
            f"warning: no problem table found in {landing}; listing alphabetically.",
            file=sys.stderr,
        )
        return sorted(problems)
    ordered = [slug for slug in ordered_rows if slug in known]
    ordered += sorted(known - set(ordered))
    return ordered


def run_test_suite() -> Path:
    """Run the full pytest suite, returning the path of the junit XML report.

    pytest exit codes 0 (all passed) and 1 (some failed) are both fine: the
    report is what we read. Anything else means the run itself broke.
    """
    with tempfile.NamedTemporaryFile(prefix="progress-", suffix=".xml", delete=False) as output:
        report = Path(output.name)
    command = [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"]
    result = subprocess.run(
        command, cwd=PRACTICE_DIR, capture_output=True, text=True, check=False
    )
    if result.returncode not in (0, 1) or not report.stat().st_size:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        report.unlink(missing_ok=True)
        raise SystemExit(
            f"error: pytest run failed (exit {result.returncode}); see output above. "
            "Try `uv run pytest -q` from practice/ to reproduce."
        )
    return report


def statuses_from_report(report: Path, problems: list[str]) -> dict[str, str]:
    """Derive each problem's status from the junit XML report.

    The junit classname's trailing two segments (`<slug>.test_<slug>`) name
    the problem module regardless of whether the module path carries a bank
    segment (`leetcode.two_sum.test_two_sum` post-move,
    `two_sum.test_two_sum` flat), so both layouts attribute their results.
    Reference tests may live in separate modules or alongside personal tests.
    """
    counts: dict[str, dict[str, int]] = {
        slug: {"passed": 0, "skipped": 0, "failed": 0} for slug in problems
    }
    known = set(problems)
    for case in ET.parse(report).getroot().iter("testcase"):
        segments = (case.get("classname") or "").split(".")
        if len(segments) < 2:
            continue
        slug, module = segments[-2:]
        test_name = (case.get("name") or "").split("[", 1)[0]
        if (
            slug not in known
            or module.startswith("test_reference_")
            or test_name.startswith("test_reference_")
        ):
            continue
        if case.find("skipped") is not None:
            outcome = "skipped"
        elif case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        else:
            outcome = "passed"
        counts[slug][outcome] += 1
    statuses: dict[str, str] = {}
    for slug, count in counts.items():
        total = sum(count.values())
        if total and count["passed"] == total:
            statuses[slug] = STATUS_SOLVED
        elif count["failed"] or count["passed"]:
            statuses[slug] = STATUS_ATTEMPTED
        else:
            statuses[slug] = STATUS_UNSOLVED
    return statuses


def last_practiced(record: dict) -> Optional[date]:
    """Latest of solved_date and rated_date, or None with no history."""
    dates = []
    for field in ("solved_date", "rated_date"):
        value = record.get(field)
        if value:
            try:
                dates.append(date.fromisoformat(value))
            except ValueError:
                pass  # a hand-edited bad date should not crash the tool
    return max(dates) if dates else None


def review_interval(record: dict) -> int:
    """Review interval in days for a problem, from its confidence rating."""
    return REVIEW_INTERVALS.get(record.get("confidence"), UNRATED_SOLVED_INTERVAL)


def due_entries(state: dict, ordered: list[str], today: date) -> list[tuple[int, str, dict]]:
    """Problems due for review as (days_overdue, slug, record), most overdue first."""
    entries = []
    for slug in ordered:
        if slug in state.get("reviews", {}):
            continue
        record = state["problems"].get(slug, {})
        if record.get("status") != STATUS_SOLVED and not record.get("rated_date"):
            continue
        practiced = last_practiced(record)
        if practiced is None:
            continue
        overdue = (today - practiced - timedelta(days=review_interval(record))).days
        if overdue >= 0:
            entries.append((overdue, slug, record))
    entries.sort(key=lambda entry: -entry[0])
    return entries


def describe(record: dict, today: date) -> str:
    """One-line annotation: confidence plus days since solved."""
    parts = []
    if record.get("confidence"):
        parts.append(record["confidence"])
    if record.get("solved_date"):
        days = (today - date.fromisoformat(record["solved_date"])).days
        parts.append(f"solved {days}d ago")
    return f"  ({', '.join(parts)})" if parts else ""


def review_queue(state: dict, ordered: list[str], today: date) -> list[tuple[int, str, str]]:
    entries = [
        (overdue, slug, record.get("confidence", "unrated"))
        for overdue, slug, record in due_entries(state, ordered, today)
    ]
    for card_id, record in state.get("reviews", {}).items():
        if record["due"]:
            overdue = (today - date.fromisoformat(record["due"])).days
            if overdue >= 0:
                entries.append((overdue, card_id, f"{interview_review.INTERVALS[record['stage']]}d stage"))
    return sorted(entries, key=lambda entry: -entry[0])


def print_due(state: dict, ordered: list[str], today: date) -> None:
    entries = review_queue(state, ordered, today)
    print("Due for review:")
    if not entries:
        print("  nothing due")
    for overdue, card_id, detail in entries:
        when = "due today" if overdue == 0 else f"{overdue}d overdue"
        print(f"  {card_id}  ({detail}, {when})")


def cmd_scan(_args: argparse.Namespace) -> int:
    problems = discover_problems()
    state = load_state()
    print(f"running the test suite across {len(problems)} problems...")
    report = run_test_suite()
    try:
        statuses = statuses_from_report(report, problems)
    finally:
        report.unlink(missing_ok=True)
    today = date.today().isoformat()
    changes = []
    for slug, status in statuses.items():
        record = state["problems"].setdefault(slug, {})
        previous = record.get("status", STATUS_UNSOLVED)
        if previous != status:
            changes.append(f"  {slug}: {previous} -> {status}")
        record["status"] = status
        record["last_scan"] = today
        if status == STATUS_SOLVED and not record.get("solved_date"):
            record["solved_date"] = today
    save_state(state)
    totals = {s: sum(1 for v in statuses.values() if v == s) for s in
              (STATUS_SOLVED, STATUS_ATTEMPTED, STATUS_UNSOLVED)}
    print(
        f"scan complete: {totals[STATUS_SOLVED]} solved, "
        f"{totals[STATUS_ATTEMPTED]} attempted, {totals[STATUS_UNSOLVED]} unsolved "
        f"(of {len(problems)})"
    )
    if changes:
        print("changes since last scan:")
        print("\n".join(sorted(changes)))
    else:
        print("no changes since last scan.")
    return 0


def cmd_rate(args: argparse.Namespace) -> int:
    problems = discover_problems()
    if args.slug not in problems:
        hint = difflib.get_close_matches(args.slug, problems, n=3)
        suggestion = f" Did you mean: {', '.join(hint)}?" if hint else ""
        print(
            f"error: unknown problem '{args.slug}'.{suggestion} "
            "Slugs are the problem directory names inside practice/leetcode/ "
            "and practice/amazon/ (e.g. two_sum).",
            file=sys.stderr,
        )
        return 1
    if args.level not in REVIEW_INTERVALS:
        print(
            f"error: unknown confidence level '{args.level}'. "
            f"Choose one of: {', '.join(CONFIDENCE_LEVELS)} "
            "(how the solve felt, easiest to hardest: solid, shaky, struggled).",
            file=sys.stderr,
        )
        return 1
    state = load_state()
    record = state["problems"].setdefault(args.slug, {})
    record["confidence"] = args.level
    record["rated_date"] = date.today().isoformat()
    save_state(state)
    interval = REVIEW_INTERVALS[args.level]
    print(f"rated {args.slug} as {args.level}; next review in {interval} days.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    problems = discover_problems()
    state = load_state()
    ordered = canonical_order(problems)
    today = date.today()
    by_status: dict[str, list[str]] = {
        STATUS_SOLVED: [], STATUS_ATTEMPTED: [], STATUS_UNSOLVED: []
    }
    for slug in ordered:
        status = state["problems"].get(slug, {}).get("status", STATUS_UNSOLVED)
        by_status.setdefault(status, []).append(slug)
    print(
        f"Progress: {len(by_status[STATUS_SOLVED])} solved, "
        f"{len(by_status[STATUS_ATTEMPTED])} attempted, "
        f"{len(by_status[STATUS_UNSOLVED])} unsolved (of {len(problems)})"
    )
    for status in (STATUS_SOLVED, STATUS_ATTEMPTED, STATUS_UNSOLVED):
        slugs = by_status[status]
        print(f"\n{status.capitalize()} ({len(slugs)}):")
        if not slugs:
            print("  none")
        for slug in slugs:
            print(f"  {slug}{describe(state['problems'].get(slug, {}), today)}")
    print()
    print_due(state, ordered, today)
    return 0


def cmd_due(_args: argparse.Namespace) -> int:
    problems = discover_problems()
    state = load_state()
    print_due(state, canonical_order(problems), date.today())
    return 0


def cmd_cards(args: argparse.Namespace) -> int:
    cards = interview_review.load_cards()
    for card_id, card in cards.items():
        if args.kind is None or card["kind"] == args.kind:
            print(f"{card_id}  {card['title']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cards = interview_review.load_cards()
    card = cards.get(interview_review.canonical_card_id(args.id))
    if card is None and args.id in discover_problems():
        print(args.id)
        print(f"Write-up: ../docs/{'amazon' if args.id.startswith('amazon-') else 'leetcode'}/{args.id}.md")
        return 0
    if card is None:
        raise SystemExit(f"unknown card: {args.id}")
    print(card["title"])
    if "question" in card:
        print(card["question"])
    if args.answer:
        print(card["answer"] if "answer" in card else card["solution"])
        if card.get("effect"):
            print(f'效果验证\n{card["effect"]}')
    if card.get("url") and (args.answer or card["kind"] == "algorithm"):
        print(card["url"])
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    args.id = interview_review.canonical_card_id(args.id)
    if args.id not in interview_review.load_cards() and args.id not in discover_problems():
        raise SystemExit(f"unknown card: {args.id}")
    try:
        record = save_review(args.id, args.result, args.note)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    due = record["due"] or "none"
    print(f"{args.id}: {args.result}; next review: {due}")
    return 0


@contextmanager
def lock_state():
    with STATE_FILE.with_suffix(".lock").open("a") as state_lock:
        fcntl.flock(state_lock, fcntl.LOCK_EX)
        yield


def save_review(card_id: str, result: str, note: str) -> dict:
    with lock_state():
        state = load_state()
        reviews = state.setdefault("reviews", {})
        record = interview_review.record_review(reviews.get(card_id), result, date.today(), note)
        reviews[card_id] = record
        save_state(state)
    return record


def delete_attempt(card_id: str, position: int, expected_history: str) -> None:
    with lock_state():
        state = load_state()
        reviews = state.get("reviews", {})
        attempts = reviews.get(card_id, {}).get("attempts", [])
        if interview_review.history_version(attempts) != expected_history or not 0 <= position < len(attempts):
            raise ValueError("记录已变化，请刷新后重试。")
        remaining = attempts[:position] + attempts[position + 1:]
        if remaining:
            reviews[card_id] = interview_review.replay_attempts(remaining)
        else:
            del reviews[card_id]
        save_state(state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="progress.py",
        description="Track solved problems, confidence, and spaced-repetition reviews.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="run the test suite and record per-problem status")
    scan.set_defaults(func=cmd_scan)
    rate = sub.add_parser("rate", help="record a confidence rating for a problem")
    rate.add_argument("slug", help="problem directory name, e.g. two_sum")
    rate.add_argument("level", help=f"confidence: {', '.join(CONFIDENCE_LEVELS)}")
    rate.set_defaults(func=cmd_rate)
    status = sub.add_parser("status", help="show the full board in canonical study order")
    status.set_defaults(func=cmd_status)
    due = sub.add_parser("due", help="show only the problems due for review")
    due.set_defaults(func=cmd_due)
    cards = sub.add_parser("cards", help="list Grind 75 and interview cards")
    cards.add_argument("--kind", choices=interview_review.KINDS)
    cards.set_defaults(func=cmd_cards)
    show = sub.add_parser("show", help="show a card; add --answer to reveal the answer")
    show.add_argument("id")
    show.add_argument("--answer", action="store_true")
    show.set_defaults(func=cmd_show)
    review = sub.add_parser("review", help="log an attempt and update the 3/10/30-day queue")
    review.add_argument("id")
    review.add_argument("result", choices=interview_review.RESULTS)
    review.add_argument("--note", default="")
    review.set_defaults(func=cmd_review)
    return parser


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    if arguments.command in {"scan", "rate"}:
        with lock_state():
            raise SystemExit(arguments.func(arguments))
    raise SystemExit(arguments.func(arguments))
