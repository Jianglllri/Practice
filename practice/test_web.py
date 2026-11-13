"""Exercise the local web form against isolated progress data."""

import json
from contextlib import closing
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode

import interview_review
import progress
import web


def test_web_review_shares_cli_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "STATE_FILE", tmp_path / "progress.json")
    today = date.today()
    progress.save_state({
        "schema": 1,
        "problems": {
            "two_sum": {"status": "solved", "solved_date": (today - timedelta(days=14)).isoformat()}
        },
    })
    with ThreadingHTTPServer(("127.0.0.1", 0), web.PracticeHandler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as connection:
                connection.request("GET", "/")
                response = connection.getresponse()
                html = response.read().decode()
                assert response.status == 200
                assert "今天到期" in html and "LC 1 · 两数之和" in html and "已完成" in html
                assert "Doocs 中文题解" in html and "Deriving the Solution" not in html
                connection.request("GET", "/?view=project")
                html = connection.getresponse().read().decode()
                assert "<details><summary>查看题解</summary>" in html
                form = urlencode({
                    "token": web.TOKEN, "id": "project:rag-regression", "result": "hinted",
                    "view": "project", "note": "漏答 <召回率>",
                })
                connection.request("POST", "/review", form, {
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                response = connection.getresponse()
                response.read()
                assert response.status == 303
                connection.request("GET", response.getheader("Location"))
                assert "练习记录已保存" in connection.getresponse().read().decode()
                connection.request("GET", "/?view=mistakes")
                assert "漏答 &lt;召回率&gt;" in connection.getresponse().read().decode()
            state = json.loads(progress.STATE_FILE.read_text(encoding="utf-8"))
            assert state["problems"]["two_sum"]["status"] == "solved"
            review = state["reviews"]["project:rag-regression"]
            assert review["attempts"][0]["note"] == "漏答 <召回率>"
            queue = progress.review_queue(state, ["two_sum"], today + timedelta(days=3))
            assert {entry[1] for entry in queue} == {"two_sum", "project:rag-regression"}
            form = urlencode({
                "token": web.TOKEN, "id": "project:rag-regression", "view": "mistakes",
                "position": "0", "version": interview_review.history_version(review["attempts"]),
            })
            with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as connection:
                connection.request("POST", "/delete", form, {"Content-Type": "application/x-www-form-urlencoded"})
                response = connection.getresponse()
                response.read()
                assert response.status == 303
                connection.request("GET", response.getheader("Location"))
                assert "暂无记录" in connection.getresponse().read().decode()
            assert "project:rag-regression" not in progress.load_state()["reviews"]
        finally:
            server.shutdown()
            worker.join()


def test_run_python_does_not_overwrite_solution():
    import code_runner

    path = code_runner.solution_path("two_sum")
    original = path.read_bytes()
    correct = """
class Solution:
    def twoSum(self, nums, target):
        for left, first in enumerate(nums):
            for right in range(left + 1, len(nums)):
                if first + nums[right] == target:
                    return [left, right]
"""
    assert "3 passed" in code_runner.run_solution(path, correct, "examples")
    broken = correct.replace("return [left, right]", "return [0, 0]")
    output = code_runner.run_solution(path, broken, "debug")
    assert "1 failed" in output and "method" in output and "case" in output
    assert path.read_bytes() == original


def test_delete_attempt_recomputes_review_and_preserves_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "STATE_FILE", tmp_path / "progress.json")
    progress.save_state({"problems": {"two_sum": {"status": "solved"}}})
    first = progress.save_review("two_sum", "hinted", "保留")
    latest = progress.save_review("two_sum", "missed", "删除")
    progress.delete_attempt("two_sum", 1, interview_review.history_version(latest["attempts"]))
    state = progress.load_state()
    assert state["reviews"]["two_sum"] == first
    assert state["problems"]["two_sum"]["status"] == "solved"
    progress.delete_attempt("two_sum", 0, interview_review.history_version(first["attempts"]))
    assert "two_sum" not in progress.load_state()["reviews"]


def test_topic_filters_preserve_existing_card_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "STATE_FILE", tmp_path / "progress.json")
    models = web.render_page("model", "model:bm25", topic="search")
    assert "BM25 与混合检索" in models
    assert "LoRA 与全量微调" not in models
    papers = web.render_page("paper", "paper:2611.17167", topic="agent")
    assert "长程 Agent 中的 Actor" in papers
    assert "FOAM 如何降低 SOAP" not in papers


def test_custom_case_returns_output_and_trace():
    import code_runner

    path = code_runner.solution_path("two_sum")
    code = "class Solution:\n    def twoSum(self, nums, target):\n        pair = [0, 1]\n        return pair\n"
    case = {"id": "custom", "args": [[4, 5], 9], "expected": [0, 1]}
    result = code_runner.run_custom_case(path, code, case, True)
    assert result["actual"] == "[0, 1]"
    assert any(step["line"] == 4 and step["locals"]["pair"] == "[0, 1]" for step in result["trace"])


def test_custom_case_reuses_linked_list_adapter():
    import code_runner

    path = code_runner.solution_path("merge_two_sorted_lists")
    code = "class Solution:\n    def mergeTwoLists(self, left, right):\n        return right\n"
    case = {"id": "custom", "args": [[], [4, 8]], "expected": [4, 8]}
    result = code_runner.run_custom_case(path, code, case, False)
    assert result["actual"] == "[4, 8]"


def test_qwen_and_interview_algorithms_are_discoverable(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "STATE_FILE", tmp_path / "progress.json")
    for view, card_id, title in [
        ("model", "model:qwen-tools", "Qwen-Agent"),
        ("project", "project:qwen-rag", "Qwen 知识库 Agent"),
        ("paper", "paper:qwen3-8-27b", "混合注意力与多模态推理"),
    ]:
        assert title in web.render_page(view, card_id, topic="qwen")
    selected = web.render_page("algorithm", "daily_temperatures", topic="interview")
    assert "16 题" in selected and "每日温度" in selected and "面试追问" in selected
    assert "75 题" in web.render_page("algorithm", "two_sum")
