"""Draw and validate a local mock interview round."""

from collections import defaultdict
from random import sample
from secrets import token_hex

from code_runner import solution_path


def draw(cards: dict[str, dict], algorithm_count: int) -> str:
    algorithms = [key for key, card in cards.items()
                  if card["kind"] == "algorithm" and card.get("solution") and solution_path(key)]
    by_topic = defaultdict(list)
    for key, card in cards.items():
        if card["kind"] == "model" and card.get("question") and card.get("answer"):
            by_topic[card.get("topic") or "general"].append(key)
    topics = sample(list(by_topic), min(6, len(by_topic)))
    theory = [sample(by_topic[topic], 1)[0] for topic in topics]
    if len(theory) < 6:
        selected = set(theory)
        remaining = [key for group in by_topic.values() for key in group if key not in selected]
        theory.extend(sample(remaining, 6 - len(theory)))
    return ",".join([token_hex(8), *sample(algorithms, algorithm_count), *theory])


def question_ids(round_id: str, cards: dict[str, dict]) -> list[str]:
    nonce, _, questions = round_id.partition(",")
    keys = questions.split(",")
    if (len(nonce) != 16 or any(character not in "0123456789abcdef" for character in nonce)
            or len(keys) not in {8, 9} or len(set(keys)) != len(keys)):
        raise ValueError("本轮题单无效。")
    for key in keys[:-6]:
        card = cards.get(key, {})
        if card.get("kind") != "algorithm" or not card.get("solution") or not solution_path(key):
            raise ValueError("本轮算法题不可用。")
    for key in keys[-6:]:
        card = cards.get(key, {})
        if card.get("kind") != "model" or not card.get("question") or not card.get("answer"):
            raise ValueError("本轮八股题不可用。")
    return keys
