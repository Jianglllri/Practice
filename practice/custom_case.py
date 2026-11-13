"""Execute a single custom case using the problem's local debug adapter."""

import ast
import json
import inspect
import reprlib
import sys
from pathlib import Path


def read_examples(path: Path) -> list[dict]:
    for filename in ("cases.json", "cases_full.json"):
        source = path.with_name(filename)
        if source.is_file():
            cases = json.loads(source.read_text(encoding="utf-8"))
            if cases:
                return cases[:5]
    return []


def read_case(path: Path) -> dict:
    return next(iter(read_examples(path)), {})


def argument_names(path: Path, example: dict) -> list[str]:
    arguments = example.get("args", [])
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Solution":
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and not method.name.startswith("_"):
                    names = [arg.arg for arg in [*method.args.posonlyargs, *method.args.args]][1:]
                    if len(names) == len(arguments):
                        return names
    return []


def execute(payload: dict) -> dict:
    path = Path("solution.py").resolve()
    source = ast.parse(payload["code"])
    case = payload["case"]
    namespace = {"__file__": str(path), "__name__": "custom_solution"}
    adapter = ast.parse(payload["adapter"])
    playground = next(
        (node for node in adapter.body if isinstance(node, ast.If)
         and ast.unparse(node.test) == "__name__ == '__main__'"),
        None,
    )
    actual = []
    trace = []

    def capture(value: object) -> None:
        try:
            rendered = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            rendered = reprlib.repr(value)
        actual.append(rendered if len(rendered) <= 12000 else rendered[:12000] + "…")

    def record(frame, event: str, _value: object):
        if (event == "line" and frame.f_code.co_filename == str(path)
                and frame.f_code.co_flags & inspect.CO_OPTIMIZED and len(trace) < 250):
            trace.append({
                "line": frame.f_lineno,
                "locals": {key: reprlib.repr(value) for key, value in list(frame.f_locals.items())[:20]},
            })
        return record

    if payload["trace"]:
        sys.settrace(record)
    try:
        exec(compile(source, str(path), "exec"), namespace)
        if playground:
            for node in ast.walk(playground):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "pick_case":
                        node.func.id = "custom_input"
                        node.args = []
                        node.keywords = []
                    elif node.func.id == "print" and node.args and isinstance(node.args[0], ast.JoinedStr):
                        parts = node.args[0].values
                        if (len(parts) == 2 and isinstance(parts[0], ast.Constant)
                                and str(parts[0].value).startswith("got:") and isinstance(parts[1], ast.FormattedValue)):
                            node.func.id = "capture_result"
                            node.args = [parts[1].value]
            for node in adapter.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    exec(compile(ast.Module(body=[node], type_ignores=[]), "<case adapter>", "exec"), namespace)
            namespace.update(custom_input=lambda: case, capture_result=capture)
            exec(compile(ast.Module(body=playground.body, type_ignores=[]), "<case adapter>", "exec"), namespace)
        else:
            solution = namespace["Solution"]()
            methods = [name for name in vars(type(solution)) if not name.startswith("_") and callable(getattr(solution, name))]
            if len(methods) != 1 or "args" not in case:
                raise ValueError("此题需要 solution.py 中原有的本地调试入口来转换输入。")
            capture(getattr(solution, methods[0])(*case["args"]))
        if not actual:
            raise ValueError("没有得到输出，请检查方法是否已实现。")
    finally:
        sys.settrace(None)
    return {"actual": actual[-1], "trace": trace, "limitReached": len(trace) == 250}


if __name__ == "__main__":
    import traceback
    from contextlib import redirect_stdout

    try:
        with redirect_stdout(sys.stderr):
            result = execute(json.loads(sys.stdin.read()))
    except Exception:
        result = {"error": traceback.format_exc()[-6000:]}
    print(json.dumps(result, ensure_ascii=False))
