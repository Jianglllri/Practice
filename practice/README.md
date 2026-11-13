# Practice Workspace

A `pytest` workspace for practicing the problems in this repository yourself: the Grind 75 and NeetCode 150 LeetCode lists and the Amazon OA bank. Each problem gets a directory you solve in, debug through, and test. Every `solution.py` is an unsolved stub: it raises `NotSolved` until you implement it, and it links to the matching write-up, at `../docs/leetcode/<slug>.md` for the LeetCode track and `../docs/amazon/<slug>.md` for the Amazon bank, whose page links back, so you can go back and forth. About half the LeetCode folders and a small subset of the Amazon ones additionally carry a `reference.py`, the write-up's own solution kept next to the harness so its authored case files stay checkable; treat it as the answer key and stay out of it until after your own attempt, with some folders adding a `test_reference_<slug>.py` that checks it.

## Get a copy

Your attempts live on your own `practice` branch, created from the study guide's `main` branch, so they never touch the guide. Fork [ThoDHa/tech-interview-prep](https://github.com/ThoDHa/tech-interview-prep) on GitHub, clone your fork, and create the branch from `main`:

```bash
git clone https://github.com/<your-username>/tech-interview-prep.git
cd tech-interview-prep
git switch -c practice main
```

This creates a local `practice` branch at `main`'s tip and switches to it. The repository also carries a `practice` branch holding the maintainer's own worked attempts; leave it alone and build on `main`.

## Layout

```text
practice/
├── harness.py                 # shared helpers (ListNode/TreeNode/graph builders, case loader, pick_case)
├── progress.py                # progress tracker (scan, rate, status, due)
├── pyproject.toml             # uv project (pytest dependency)
├── pytest.ini                 # markers, import path, and other pytest settings
├── leetcode/                  # Grind 75 + NeetCode 150 problems
│   └── <slug>/                # the four files below; some folders add reference.py + test_reference_<slug>.py
│       ├── solution.py        # YOUR attempt: solve here; run it directly to debug a case
│       ├── cases.json         # simple cases: the LeetCode examples ("Run")
│       ├── cases_full.json    # full cases: the corner-case gauntlet ("Submit")
│       └── test_<slug>.py     # runs your solution against both case sets
└── amazon/                    # Amazon OA bank
    └── <slug>/                # solution.py + cases.json + test_<slug>.py; a few folders add cases_full.json + reference.py + a reference test
```

## Setup (uv)

```bash
cd practice
uv sync           # creates .venv and installs pytest
```

## The practice loop

1. Open `leetcode/<slug>/solution.py`. The header links to the write-up at `../../docs/leetcode/<slug>.md`: read the problem there.
2. Implement the method.
3. **Debug it inside the file.** Each `solution.py` has a `__main__` block that runs one case and prints input / expected / actual. Set a breakpoint in your method, pick the case (edit the `CASE` id near the bottom), and run/debug the file directly:

   ```bash
   uv run python leetcode/two_sum/solution.py
   ```

   On an untouched stub the `__main__` block raises `NotSolved`: there is nothing to debug until the method exists.

4. **Test it.** Two case sets, mirroring LeetCode's two buttons:

   ```bash
   uv run pytest leetcode/two_sum/             # both sets
   uv run pytest leetcode/two_sum/ -m simple   # "Run": just the examples
   uv run pytest leetcode/two_sum/ -m full     # "Submit": the full gauntlet
   uv run pytest                               # everything
   ```

   An unsolved `solution.py` raises `NotSolved`, so its tests **skip** rather than fail. Once you implement it, they run for real (red → green).

5. To study the approaches, open `../docs/leetcode/<slug>.md` (linked from the top of `solution.py`).

Amazon problems follow the same loop with paths like `amazon/amazon-aggressive-cows/` and its single case set:

```bash
uv run python amazon/amazon-aggressive-cows/solution.py
uv run pytest amazon/amazon-aggressive-cows/
```

## Case sets: Run vs Submit

| File | Marker | Role |
|------|--------|------|
| `cases.json` | `simple` | The problem's own examples where they parse, otherwise a few promoted gauntlet cases. Fast feedback while you iterate. |
| `cases_full.json` | `full` | Examples **plus** a comprehensive corner-case gauntlet (empties, single elements, negatives, duplicates, boundary values, large inputs). |

`cases_full.json` is a thorough corner-case suite built to each problem's constraints. LeetCode's literal hidden tests are not public, but this set targets the same failure modes. Amazon problems use no markers: most ship only `cases.json`, so a plain `uv run pytest amazon/<slug>/` is all they need, and the few that also carry `cases_full.json` and a reference test run their whole folder with that same plain command.

## Tracking your progress

`progress.py` is a small stdlib-only tracker that remembers which problems you have solved, how confident each solve felt, and which ones are due for a spaced-repetition review. Its state lives in `.progress.json` next to it (personal, gitignored, and never read by the tests).

```bash
uv run python progress.py scan             # run the suite, record per-problem status
uv run python progress.py rate <slug> <solid|shaky|struggled>
uv run python progress.py status           # full board in canonical study order
uv run python progress.py due              # just the review queue
```

**Status model.** `scan` runs the full test suite and reports it honestly: a problem is `solved` only while every test passes, `attempted` when any test fails (or only some pass), and `unsolved` when everything skips. The date of the first successful solve is recorded automatically. If a solved problem later reverts to the stub, its status drops back to `unsolved`, but the solve date and rating history are kept.

**Confidence and review.** After solving, rate how it felt with `rate <slug> <level>`. The rating sets the spaced-repetition interval:

| Confidence | Review after |
|------------|--------------|
| `struggled` | 2 days |
| `shaky` | 7 days |
| `solid` | 21 days |
| solved but unrated | 14 days |

A problem is due once that many days have passed since you last practiced it (the later of the solve date and the rating date). `due` lists the queue, most overdue first: re-solve it, rate it again, and the clock resets.

## Case format

Both `cases.json` and `cases_full.json` are lists of cases. For most problems a case is `{"id": ..., "args": [...], "expected": ...}` where `args` is the positional argument list and `expected` the return value. Problems with linked lists, trees, graphs, or design-operation sequences store plain JSON in the case files and the test module marshals it via the `harness` helpers.

## 中文题解与面试复习

在 `practice/` 下运行以下命令：

```bash
uv run --no-sync python progress.py cards --kind algorithm
uv run --no-sync python progress.py show two_sum --answer
uv run --no-sync python progress.py cards --kind model
uv run --no-sync python progress.py cards --kind project
uv run --no-sync python progress.py cards --kind paper
uv run --no-sync python progress.py show project:rag-regression
uv run --no-sync python progress.py show project:rag-regression --answer
uv run --no-sync python progress.py review project:rag-regression hinted --note "漏答了召回层指标"
uv run --no-sync python progress.py due
```

Grind 75 的 75 道正选题带 Doocs 中文题解链接。模型、项目和论文卡可先用
`show` 自答，再用 `--answer` 查看要点与来源。论文卡是截至 2026-11-13 的首批样例。

每次用 `review <ID> missed|hinted|passed` 自评。卡住或用了提示会排到 3 天后。
在到期日或之后独立通过，依次安排 10 天、30 天；最后一次通过后移出队列。
首次独立做出也无需排期。算法题可在本地重写、跑测试后再自评。
旧 `rate` 记录仍可查询。同一题使用 `review` 后以新队列为准。

## 本地网页

在 `practice/` 中运行：

```bash
uv run --no-sync python web.py
```

打开 [面试练习室](http://127.0.0.1:8765)。首页显示今日到期及逾期的题。通过顶部分类选题，
在作答区自答，展开「查看题解」核对，再选择练习结果并保存备注。错题记录保留历次结果。
作答区草稿仅在当前页面使用，复盘备注随结果保存。网页和命令行共用 `.progress.json`。
端口被占用时可传 `--port 8766`。

算法题可直接编辑 Python，运行示例或全部个人测试。「调试失败用例」显示首个失败的
调用栈和局部变量。运行使用临时副本。选择「保存到 solution.py」后，可使用页面提供的
本地 `pdb` 命令单步运行示例，或用 pytest 在首个失败处进入调试器。
网页会以当前用户权限执行代码，请运行自己信任的 Python。

在练习记录中展开「删除此记录」并确认，即可删除单次尝试和备注。复习日期会按剩余
记录重新计算，测试扫描结果保留。

模型八股和论文可按 LLM、Agent、搜索、推荐、机器学习筛选。论文卡为手工核对的固定题单。
Python3 编辑器在本地加载，支持行号、语法高亮、四空格缩进、括号配对和撤销。

如需重建编辑器，复制 `editor.package.json` 和 `editor.package-lock.json` 到临时目录，
分别命名为 `package.json` 和 `package-lock.json`，把 `editor.js` 放到同一目录。
在临时目录运行 `npm ci` 和 `npx esbuild editor.js --bundle --minify --legal-comments=none --outfile=editor.bundle.js`，
再将产物复制回 `practice/`。

「自定义测试用例」从题目的示例填入 JSON，可编辑输入和预期结果。运行后会并排显示
实际输出和手填的预期结果。修改输入后，请为新用例填写预期结果。
点击编辑器行号左侧添加回放断点，再点「记录调试轨迹」。可单步查看执行前的局部变量，
或跳到下一个断点。回放最多记录 250 步；实时交互仍可使用本地 pdb。

「算法题」里的「高频面试题」是参考力扣热题 100 和 Grind 75 精选的练习入口。
同一题在不同题单中使用同一个 ID，代码、练习记录与复习安排共用。
模型八股、项目追问和近期论文可通过 Qwen 筛选查看对应专题。
