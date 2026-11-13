"""Serve the interview practice interface on loopback."""

import argparse
import json
import re
import secrets
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from random import choice
from urllib.parse import parse_qs, urlencode, urlsplit

import code_runner
import custom_case
import interview_review
import mock_interview
import progress

DIRECTORY = Path(__file__).resolve().parent
CATEGORIES = {"algorithm": "算法题", "model": "模型八股", "project": "项目追问", "paper": "近期论文"}
RESULTS = {"missed": "没做出", "hinted": "用了提示", "passed": "独立完成"}
TOKEN = secrets.token_urlsafe(32)
STYLE_NONCE = secrets.token_urlsafe(24)
TOPICS = {"industry": "业务实践专项", "qwen": "Qwen", "llm": "LLM", "agent": "Agent", "search": "搜索", "recommendation": "推荐", "ml": "机器学习"}


def page_url(view: str, card_id: str = "", **options: str) -> str:
    return "/?" + urlencode({"view": view, "id": card_id, **options})


def catalog(state: dict) -> dict[str, dict]:
    cards = interview_review.load_cards()
    for card_id in (state["problems"] | state.get("reviews", {})):
        if card_id not in cards and re.fullmatch(r"[a-z0-9_-]+", card_id):
            cards[card_id] = {"kind": "algorithm", "title": card_id.replace("_", " ")}
    return cards


def algorithm_prompt(card_id: str) -> str:
    bank = "amazon" if card_id.startswith("amazon-") else "leetcode"
    path = DIRECTORY.parent / "docs" / bank / f"{card_id}.md"
    if not path.is_file():
        return ""
    source = path.read_text(encoding="utf-8")
    statement = re.split(r"^## (?:Solutions?|Deriving the Solution|Comparison of Solutions|Approach|Hints?|Explanation|Intuition|Algorithm)\b",
                         source, maxsplit=1, flags=re.MULTILINE | re.IGNORECASE)[0]
    # Examples and constraints may use bold labels; keep those, omit strategy metadata.
    lines = [line for line in statement.splitlines()[1:]
             if not line.startswith(("**Pattern:", "**Algorithm:", "**Practice:", "**Easy**",
                                     "**Medium**", "**Hard**"))]
    return "\n".join(lines).strip()


def render_card(card_id: str, card: dict, state: dict, view: str,
                saved: bool, error: str, note: str,
                code: str | None, output: str, topic: str, search: str) -> str:
    review = state.get("reviews", {}).get(card_id, {})
    history = review.get("attempts", [])
    status = {"solved": "已完成", "attempted": "部分通过", "unsolved": "未做"}
    detail = status.get(state["problems"].get(card_id, {}).get("status"), "")
    next_due = review.get("due")
    if next_due:
        detail = f"{detail} · 下次复习 {next_due}" if detail else f"下次复习 {next_due}"
    prompt = card.get("question") or algorithm_prompt(card_id)
    source = ""
    if card["kind"] == "algorithm" and card.get("url"):
        source = f'<a href="{escape(card["url"])}" target="_blank" rel="noopener">打开 LeetCode 题目 ↗</a>'
    answer = ""
    if card.get("solution"):
        answer = f'<a href="{escape(card["solution"])}" target="_blank" rel="noopener">打开 Doocs 中文题解 ↗</a>'
    elif card.get("answer"):
        answer = f'<p>{escape(card["answer"])}</p>'
        if card.get("effect"):
            answer = '<h4>解决办法</h4>' + answer + f'<h4>效果验证</h4><p>{escape(card["effect"])}</p>'
        if card.get("url"):
            answer += f'<a href="{escape(card["url"])}" target="_blank" rel="noopener">查看来源 ↗</a>'
    else:
        answer = f'<a href="/writeup?id={escape(card_id)}" target="_blank" rel="noopener">查看本地题解 ↗</a>'
    if card.get("reading"):
        sections = "".join(f"<h4>{escape(heading)}</h4><p>{escape(body)}</p>"
                           for heading, body in card["reading"].items())
        answer = sections + answer
        if card.get("weights"):
            answer += f'<p><a href="{escape(card["weights"])}" target="_blank" rel="noopener">模型权重 ↗</a></p>'
    if card.get("followup"):
        answer += f'<h4>面试追问</h4><p>{escape(card["followup"])}</p>'
    if card.get("source_followup"):
        prompt += "\n\n面经追问：" + card["source_followup"]
    if card.get("github_followup"):
        prompt += "\n\nGitHub 手撕练习：" + card["github_followup"]
    if card.get("sources"):
        sources = " · ".join(
            f'<a href="{escape(source["url"])}" target="_blank" rel="noopener">{escape(source["title"])}</a>'
            for source in card["sources"]
        )
        answer += f'<p class="meta">面经来源 {sources}</p>'
    feedback = ""
    if error:
        feedback = f'<p class="feedback error" role="alert">{escape(error)}</p>'
    elif saved:
        feedback = '<p class="feedback" role="status">练习记录已保存。</p>'
    hidden = (
        f'<input type="hidden" name="token" value="{TOKEN}">'
        f'<input type="hidden" name="id" value="{escape(card_id)}">'
        f'<input type="hidden" name="view" value="{escape(view)}">'
        f'<input type="hidden" name="topic" value="{escape(topic)}">'
        f'<input type="hidden" name="q" value="{escape(search)}">'
    )
    version = interview_review.history_version(history)
    records = "".join(
        f'<li><span>{escape(attempt["date"])} · {RESULTS[attempt["result"]]}</span>'
        f'<p>{escape(attempt["note"])}</p>'
        f'<details><summary>删除此记录</summary><form method="post" action="/delete">{hidden}'
        f'<input type="hidden" name="position" value="{position}">'
        f'<input type="hidden" name="version" value="{version}">'
        f'<button class="danger">确认删除</button></form></details></li>'
        for position, attempt in reversed(list(enumerate(history)))
    )
    editor = """
          <label for="draft">作答区 <small>草稿仅在当前页面使用</small></label>
          <textarea id="draft" rows="5" placeholder="写下你的思路或答案"></textarea>"""
    path = code_runner.solution_path(card_id) if card["kind"] == "algorithm" else None
    if path:
        code = path.read_text(encoding="utf-8") if code is None else code
        report = f'<pre class="output" tabindex="0">{escape(output)}</pre>' if output else ""
        command = f"PYTHONPATH=. uv run --no-sync python -m pdb {path.relative_to(DIRECTORY)}"
        test_path = path.parent.relative_to(DIRECTORY) / f"test_{card_id}.py"
        failure_command = f"uv run --no-sync pytest -x --pdb -k 'not test_reference_' {test_path}"
        editor = f"""
          <form method="post" action="/code">{hidden}
            <div class="editor-bar"><label for="code">代码</label><span>Python3</span></div>
            <textarea id="code" name="code" data-style-nonce="{STYLE_NONCE}" class="code" rows="14" spellcheck="false" maxlength="32000">{escape(code)}</textarea>
            <div class="actions">
              <button name="mode" value="examples">运行示例</button>
              <button name="mode" value="all">运行全部</button>
              <button name="mode" value="debug">调试失败用例</button>
              <button name="mode" value="save">保存到 solution.py</button>
            </div>
            <section class="custom-case"
              data-cases="{escape(json.dumps(custom_case.read_examples(path), ensure_ascii=False))}"
              data-names="{escape(json.dumps(custom_case.argument_names(path, custom_case.read_case(path))))}">
              <h3>测试用例</h3>
              <div class="case-tabs" aria-label="选择用例"></div>
              <div id="case-fields"></div>
              <label for="case-expected">预期结果（JSON）</label>
              <textarea id="case-expected" class="code" rows="2"></textarea>
              <div class="actions">
                <button type="button" id="case-run">运行用例</button>
                <button type="button" id="case-debug">记录调试轨迹</button>
                <small>点击行号左侧设置回放断点</small>
              </div>
              <pre id="case-result" class="output" role="status" hidden></pre>
              <div id="case-trace" hidden>
                <div class="actions"><button type="button" id="trace-next">单步</button>
                <button type="button" id="trace-continue">继续到断点</button></div>
                <pre id="trace-state" class="output" aria-live="polite"></pre>
              </div>
            </section>
          </form>
          {report}
          <details><summary>用本地终端逐步调试</summary>
            <p>保存代码后，在 practice 目录运行。进入 pdb 后用 s 单步进入，n 执行下一行，p 查看变量。</p>
            <pre class="output">{escape(command)}</pre>
            <p>在第一个失败用例处进入 pdb：</p>
            <pre class="output">{escape(failure_command)}</pre>
          </details>"""
    history_html = f'<section class="history"><h3>练习记录</h3><ul>{records}</ul></section>' if records else ""
    return f"""
        <article class="card {card['kind']}">
          <div class="meta"><span>{CATEGORIES[card["kind"]]}</span> {escape(detail)}</div>
          <h2>{escape(card["title"])}</h2>
          {'<h3>问题背景</h3>' if card.get("effect") else ""}
          <div class="prompt">{escape(prompt)}</div>
          {source}
          {editor}
          <details><summary>查看题解</summary><div class="answer">{answer}</div></details>
          <form method="post" action="/review">{hidden}
            <label for="note">复盘备注</label>
            <textarea id="note" name="note" rows="2" maxlength="4000" placeholder="记下卡住的地方或下次要复习的点">{escape(note)}</textarea>
            <div class="actions">
              <button name="result" value="missed">没做出</button>
              <button name="result" value="hinted">用了提示</button>
              <button name="result" value="passed">独立完成</button>
            </div>
          </form>
          {feedback}
          {history_html}
        </article>"""


def render_mock(cards: dict[str, dict], round_id: str, submitted: dict | None) -> str:
    if not round_id:
        return f"""<article class="card">
          <h2>模拟面试</h2>
          <p>每轮随机抽取算法题和 6 道八股。算法题可运行示例，交卷后逐题对照题解。</p>
          <form method="post" action="/mock/start">
            <input type="hidden" name="token" value="{TOKEN}">
            <label for="algorithm-count">算法题数量</label>
            <select id="algorithm-count" name="count">
              <option value="random">随机 2–3 道</option><option value="2">2 道</option><option value="3">3 道</option>
            </select>
            <div class="actions"><button>开始面试</button></div>
          </form>
        </article>"""
    keys = mock_interview.question_ids(round_id, cards)
    questions = []
    for number, key in enumerate(keys, 1):
        card = cards[key]
        kind = card["kind"]
        prompt = card.get("question") or algorithm_prompt(key)
        title = escape(card["title"])
        path = code_runner.solution_path(key) if kind == "algorithm" else None
        if submitted is not None:
            response = submitted.get(f"answer-{number}", "")
            comparison = (
                f'<a href="{escape(card["solution"])}" target="_blank" rel="noopener">查看中文题解 ↗</a>'
                if path else f'<div class="prompt">{escape(card["answer"])}</div>'
            )
            if card.get("effect"):
                comparison += f'<p>{escape(card["effect"])}</p>'
            practice_link = escape(page_url("library", key))
            field = (f'<h4>我的作答</h4><div class="prompt">{escape(response) if response.strip() else "未作答"}</div>'
                     f'<h4>参考答案</h4>{comparison}<p><a href="{practice_link}">打开原题并记录复习</a></p>')
        else:
            starter = path.read_text(encoding="utf-8") if path else ""
            field = (f'<label for="answer-{number}">{"Python3 代码" if path else "我的回答"}</label>'
                     f'<textarea id="answer-{number}" name="answer-{number}" rows="{12 if path else 4}" '
                     f'class="{"code" if path else ""}" maxlength="{32000 if path else 4000}" '
                     f'spellcheck="false">{escape(starter)}</textarea>')
            if path:
                field += (f'<div class="actions"><button type="button" data-mock-run="{escape(key)}">'
                          '运行示例</button></div><pre class="output" role="status" hidden></pre>')
        questions.append(f'<section class="mock-question"><h3>{number}. {title}</h3>'
                         f'<p class="meta">{CATEGORIES[kind]}</p><div class="prompt">{escape(prompt)}</div>'
                         f'{field}</section>')
    content = "".join(questions)
    if submitted is not None:
        return (f'<article class="card"><h2>模拟面试复盘</h2>{content}'
                f'<p><a href="{page_url("mock")}">开始下一轮</a></p></article>')
    return f"""<article class="card"><h2>模拟面试</h2>
      <p>{len(keys) - 6} 道算法题 · 6 道八股</p>
      <form method="post" action="/mock/submit" data-mock-round="{escape(round_id)}">
        <input type="hidden" name="token" value="{TOKEN}">
        <input type="hidden" name="round" value="{escape(round_id)}">
        {content}<div class="actions"><button>交卷并查看题解</button></div>
      </form>
    </article>"""


def render_page(view: str, card_id: str, *, saved: bool = False,
                error: str = "", note: str = "", code: str | None = None, output: str = "", topic: str = "", search: str = "",
                round_id: str = "", submitted: dict | None = None) -> str:
    view = "industry" if view == "meituan" else view
    topic = "industry" if topic == "meituan" else topic
    card_id = interview_review.canonical_card_id(card_id)
    state = progress.load_state()
    cards = catalog(state)
    due = progress.review_queue(state, list(state["problems"]), date.today())
    views = {"library": "题库总览", "mock": "模拟面试", "industry": "业务实践专项", "due": "今日复习", **CATEGORIES, "mistakes": "错题记录"}
    view = view if view in views else "due"
    if view == "library":
        terms = search.casefold().split()
        choices = {}
        for key, card in cards.items():
            if card["kind"] == "algorithm" and "solution" not in card:
                continue
            label = " · ".join(filter(None, [
                CATEGORIES[card["kind"]], TOPICS.get(card.get("topic"), ""),
            ]))
            searchable = (label + " " + json.dumps(card, ensure_ascii=False)).casefold()
            if all(term in searchable for term in terms):
                choices[key] = label
    elif view == "industry":
        choices = {key: CATEGORIES[card["kind"]] for key, card in cards.items()
                   if card.get("topic") == "industry"}
        for key in ("lru_cache", "kth_largest_element_in_an_array", "sliding_window_maximum",
                    "model:qwen-tools", "xhs:grpo", "model:position-bias", "model:time-split"):
            if key in cards:
                choices[key] = CATEGORIES[cards[key]["kind"]]
    elif view == "due":
        choices = {key: f"逾期 {days} 天" if days else "今天到期"
                   for days, key, _ in due if key in cards}
    elif view == "mistakes":
        choices = {key: CATEGORIES[cards[key]["kind"]]
                   for key, review in state.get("reviews", {}).items()
                   if key in cards and any(attempt["result"] != "passed" for attempt in review["attempts"])}
    else:
        choices = {key: "" for key, card in cards.items() if card["kind"] == view
                   and (view != "algorithm" or "solution" in card)}
    filters = ""
    topics = {"": "Grind 75", "interview": "高频面试题", "xiaohongshu": "小红书面经"} if view == "algorithm" else {"": "全部", **TOPICS, "xiaohongshu": "小红书面经"}
    if view == "model":
        topics["github"] = "GitHub 手撕"
    source_domains = {"xiaohongshu": "www.xiaohongshu.com", "github": "github.com"}
    if topic in source_domains and view in {"algorithm", "model", "project"}:
        choices = {
            key: label for key, label in choices.items()
            if any(urlsplit(source["url"]).hostname == source_domains[topic]
                   for source in cards[key].get("sources", []))
        }
    elif view == "algorithm":
        choices = {key: label for key, label in choices.items()
                   if (cards[key].get("interview") if topic == "interview" else not cards[key].get("interview_only"))}
    elif view in {"model", "paper", "project"} and topic in TOPICS:
        choices = {key: label for key, label in choices.items() if cards[key].get("topic") == topic}
    if view in {"algorithm", "model", "paper", "project"}:
        filters = '<div class="topics">' + "".join(
            f'<a href="{escape(page_url(view, topic=key))}"'
            f' {"aria-current=page" if topic == key else ""}>{label}</a>'
            for key, label in topics.items() if (view != "project" or key in {"", "industry", "qwen", "xiaohongshu"})
            and (view != "paper" or key != "xiaohongshu")
        ) + "</div>"
    if card_id not in choices and not ((saved or error or code is not None) and card_id in cards):
        card_id = next(iter(choices), "")
    nav = "".join(
        f'<a href="{escape(page_url(key))}" {"aria-current=page" if view == key else ""}>'
        f'{label}{f" <b>{len(due)}</b>" if key == "due" else ""}</a>'
        for key, label in views.items()
    )
    items = "".join(
        f'<a href="{escape(page_url(view, key, topic=topic, q=search))}" {"aria-current=true" if key == card_id else ""}>'
        f'<span>{escape(cards[key]["title"])}</span><small>{escape(label)}</small></a>'
        for key, label in choices.items()
    )
    empty = "今天没有到期或逾期的题。" if view == "due" else "暂无记录。"
    content = (render_card(card_id, cards[card_id], state, view, saved, error, note, code, output, topic, search) if card_id
               else f'<div class="card empty"><h2>{empty}</h2><a href="/?view=algorithm">浏览算法题 →</a></div>')
    search_form = ""
    if view == "library":
        search_form = f"""
        <form class="topics" action="/" method="get">
          <input type="hidden" name="view" value="library">
          <input type="search" name="q" aria-label="搜索题库" value="{escape(search)}"
                 placeholder="搜索题目、知识点或来源" maxlength="160">
          <button>搜索</button>
        </form>"""
    workspace = (render_mock(cards, round_id, submitted) if view == "mock" else
                 f'<div class="workspace"><aside><h2>{views[view]} <small>{len(choices)} 题</small></h2>'
                 f'<div class="question-list">{items}</div></aside>{content}</div>')
    mock_script = '<script defer src="/mock_interview.js"></script>' if view == "mock" else ""
    return f"""<!doctype html>
    <html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>面试练习室</title><link rel="stylesheet" href="/style.css"><script defer src="/editor.bundle.js"></script>{mock_script}</head>
    <body><header><div><h1>面试练习室</h1></div></header>
    <main><nav aria-label="题目类别">{nav}</nav>{filters}{search_form}{workspace}
    </main></body></html>"""


class PracticeHandler(BaseHTTPRequestHandler):
    def send_content(self, content: str, mime: str = "text/html", status: int = 200) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' 'nonce-{STYLE_NONCE}'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self) -> bool:
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def do_GET(self) -> None:
        if not self.valid_host():
            self.send_error(403)
            return
        request = urlsplit(self.path)
        query = {key: values[0] for key, values in parse_qs(request.query).items()}
        if request.path == "/style.css":
            self.send_content((DIRECTORY / "web.css").read_text(encoding="utf-8"), "text/css")
        elif request.path == "/editor.bundle.js":
            self.send_content((DIRECTORY / "editor.bundle.js").read_text(encoding="utf-8"), "text/javascript")
        elif request.path == "/mock_interview.js":
            self.send_content((DIRECTORY / "mock_interview.js").read_text(encoding="utf-8"), "text/javascript")
        elif request.path == "/":
            view = query.get("view", "due")
            try:
                page = render_page(view, query.get("id", ""),
                                          saved=query.get("saved") == "1", topic=query.get("topic", ""),
                                          search=query.get("q", "")[:160], round_id=query.get("round", ""))
            except ValueError:
                if view != "mock":
                    raise
                self.send_error(400)
                return
            self.send_content(page)
        elif request.path == "/writeup" and query.get("id") in catalog(progress.load_state()):
            card_id = query["id"]
            if not re.fullmatch(r"[a-z0-9_-]+", card_id):
                self.send_error(404)
                return
            bank = "amazon" if card_id.startswith("amazon-") else "leetcode"
            path = DIRECTORY.parent / "docs" / bank / f"{card_id}.md"
            if path.is_file():
                self.send_content(path.read_text(encoding="utf-8"), "text/plain")
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if not self.valid_host():
            self.send_error(403)
            return
        is_mock = self.path in {"/mock/start", "/mock/run", "/mock/submit"}
        if not is_mock and self.path not in {"/review", "/delete", "/code", "/custom-case"}:
            self.send_error(404)
            return
        length = self.headers.get("Content-Length", "")
        max_length = 1500000 if self.path == "/mock/submit" else 350000
        if not length.isascii() or not length.isdecimal() or len(length) > 7 or int(length) > max_length:
            self.send_error(400)
            return
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(415)
            return
        try:
            form = {key: values[0] for key, values in parse_qs(
                self.rfile.read(int(length)).decode("utf-8"), max_num_fields=11 if is_mock else 9
            ).items()}
        except ValueError:
            self.send_error(400)
            return
        if form.get("token") != TOKEN:
            self.send_error(403)
            return
        if is_mock:
            self.handle_mock(form)
            return
        card_id = interview_review.canonical_card_id(form.get("id", ""))
        result = form.get("result", "")
        view, note = form.get("view", "due"), form.get("note", "").strip()
        topic = form.get("topic", "")
        search = form.get("q", "")[:160]
        card = catalog(progress.load_state()).get(card_id)
        if card is None:
            self.send_error(400)
            return
        if self.path == "/custom-case":
            path = code_runner.solution_path(card_id) if card["kind"] == "algorithm" else None
            code = form.get("code", "")
            try:
                case = json.loads(form.get("case", ""))
                sample = custom_case.read_case(path) if path else {}
                if (not path or not code.strip() or len(code) > 32000
                        or not isinstance(case, dict) or not sample
                        or case.keys() != sample.keys()):
                    raise ValueError("输入结构应与本题示例一致。")
                for key in ("args", "operations", "arguments"):
                    if key in sample and not isinstance(case[key], list):
                        raise ValueError(f"{key} 应是 JSON 数组。")
                result = code_runner.run_custom_case(path, code, case, form.get("trace") == "1")
            except ValueError as error:
                result = {"error": str(error)}
            self.send_content(json.dumps(result, ensure_ascii=False), "application/json")
            return
        if self.path == "/code":
            path = code_runner.solution_path(card_id) if card["kind"] == "algorithm" else None
            code, mode = form.get("code", ""), form.get("mode")
            if path is None or not code.strip() or len(code) > 32000 or mode not in {"examples", "all", "debug", "save"}:
                self.send_error(400)
                return
            if mode == "save":
                code_runner.save_solution(path, code)
                output = f"已保存到 {path.relative_to(DIRECTORY)}"
            else:
                output = code_runner.run_solution(path, code, mode)
            self.send_content(render_page(view, card_id, code=code, output=output, topic=topic, search=search))
            return
        try:
            if self.path == "/delete":
                progress.delete_attempt(card_id, int(form.get("position", "-1")), form.get("version", ""))
            elif result in RESULTS and len(note) <= 4000:
                progress.save_review(card_id, result, note)
            else:
                self.send_error(400)
                return
        except ValueError as error:
            self.send_content(render_page(view, card_id, error=str(error), note=note, topic=topic, search=search), status=409)
            return
        self.send_response(303)
        destination = page_url(view, card_id, topic=topic, q=search, saved="0" if self.path == "/delete" else "1")
        self.send_header("Location", destination)
        self.end_headers()

    def handle_mock(self, form: dict) -> None:
        cards = catalog(progress.load_state())
        try:
            if self.path == "/mock/start":
                count = form.get("count")
                if count not in {"2", "3", "random"}:
                    raise ValueError("算法题数量无效。")
                round_id = mock_interview.draw(cards, choice((2, 3)) if count == "random" else int(count))
                self.send_response(303)
                self.send_header("Location", page_url("mock", round=round_id))
                self.end_headers()
                return
            round_id = form.get("round", "")
            keys = mock_interview.question_ids(round_id, cards)
            if self.path == "/mock/run":
                key = form.get("id", "")
                code = form.get("code", "")
                path = code_runner.solution_path(key) if key in keys[:-6] else None
                if not path or not code.strip() or len(code) > 32000:
                    raise ValueError("请选择本轮算法题并输入代码。")
                self.send_content(code_runner.run_solution(path, code, "examples"), "text/plain")
                return
            for number, key in enumerate(keys, 1):
                maximum = 32000 if cards[key]["kind"] == "algorithm" else 4000
                if len(form.get(f"answer-{number}", "")) > maximum:
                    raise ValueError("作答超出长度限制。")
            self.send_content(render_page("mock", "", round_id=round_id, submitted=form))
        except ValueError as error:
            self.send_content(str(error), "text/plain", status=400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", options.port), PracticeHandler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
