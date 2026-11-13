"""Run learner code against the existing pytest harness."""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def solution_path(card_id: str) -> Path | None:
    if not re.fullmatch(r"[a-z0-9_-]+", card_id):
        return None
    bank = "amazon" if card_id.startswith("amazon-") else "leetcode"
    path = DIRECTORY / bank / card_id / "solution.py"
    return path if path.is_file() else None


def save_solution(path: Path, code: str) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(code.encode("utf-8"))
            temporary.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def run_solution(path: Path, code: str, mode: str) -> str:
    with tempfile.TemporaryDirectory(prefix="interview-run-") as directory:
        folder = Path(directory) / path.parent.name
        shutil.copytree(path.parent, folder, ignore=shutil.ignore_patterns("__pycache__"))
        (folder / "solution.py").write_text(code, encoding="utf-8")
        command = [
            sys.executable, "-m", "pytest", "-q", "-r", "s", "--tb=short",
            "-p", "no:cacheprovider", "-c", str(DIRECTORY / "pytest.ini"),
            str(folder / f"test_{folder.name}.py"),
        ]
        if mode == "examples" and "@pytest.mark.simple" in (folder / f"test_{folder.name}.py").read_text(encoding="utf-8"):
            command += ["-m", "simple"]
        elif mode == "debug":
            command += ["-x", "--showlocals", "--tb=long"]
        command += ["-k", "not test_reference_"]
        environment = {**os.environ, "PYTHONPATH": str(DIRECTORY), "PYTHONBREAKPOINT": "0"}
        with tempfile.TemporaryFile() as output:
            with subprocess.Popen(command, cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                  stdout=output, stderr=subprocess.STDOUT, start_new_session=True) as process:
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    return "运行超过 12 秒，已停止。"
            output.seek(0, os.SEEK_END)
            size = output.tell()
            output.seek(max(0, size - 16000))
            prefix = "输出较长，显示末尾部分。\n" if size > 16000 else ""
            return prefix + output.read().decode("utf-8", errors="replace")


def run_custom_case(path: Path, code: str, case: dict, trace: bool) -> dict:
    import json

    with tempfile.TemporaryDirectory(prefix="interview-case-") as directory:
        payload = json.dumps({"code": code, "case": case, "trace": trace,
                              "adapter": path.read_text(encoding="utf-8")})
        environment = {**os.environ, "PYTHONBREAKPOINT": "0"}
        with tempfile.TemporaryFile() as output:
            with subprocess.Popen([sys.executable, str(DIRECTORY / "custom_case.py")],
                                  cwd=directory, env=environment, stdin=subprocess.PIPE,
                                  stdout=output, stderr=subprocess.DEVNULL,
                                  start_new_session=True) as process:
                try:
                    process.communicate(payload.encode(), timeout=12)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    return {"error": "运行超过 12 秒，已停止。"}
            output.seek(0)
            try:
                return json.loads(output.read(4_000_000))
            except ValueError:
                return {"error": "Python 进程没有返回可读结果。"}
