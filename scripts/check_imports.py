# -*- coding: utf-8 -*-
"""运行时导入冒烟测试：验证 requirements.txt 里的版本在真实导入时可用。

为什么不满足于 `pip install --dry-run`：
  依赖解析只证明「这组版本能装上、彼此不冲突」，不证明「装上之后 import 不炸」。
  跨版本升级真正会踩的坑恰恰在后者：符号被移除、子模块被重命名、可选依赖的
  导入路径变化等，解析阶段全都看不出来。本脚本补上这块。

为什么分两组：
  torch / transformers / docling / paddleocr 这类包体积以 GB 计，
  全量安装会让 CI 变得不划算。故分两级：
    CORE  —— 严格校验，缺一个即失败；覆盖 Tier 1 安全升级涉及的全部包。
    HEAVY —— 宽松报告，装不上只提示不失败，避免 CI 被体积绑架。

pin 的来源：
  用 --emit-pins 从 requirements.txt 里直接抽出 CORE 组的固定版本，
  保证「被测版本」与「仓库声明版本」不会漂移。
"""
from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

# (发行包名, 可接受的模块名候选)。模块名与包名不一致的在此显式列出，
# 例如 PyMuPDF 的模块名是 fitz、python-docx 的模块名是 docx。
CORE: list[tuple[str, tuple[str, ...]]] = [
    ("fastapi", ("fastapi",)),
    ("pydantic", ("pydantic",)),
    ("pydantic-settings", ("pydantic_settings",)),
    ("SQLAlchemy", ("sqlalchemy",)),
    ("langchain-core", ("langchain_core",)),
    ("langchain-text-splitters", ("langchain_text_splitters",)),
    ("langchain-community", ("langchain_community",)),
    ("langchain-openai", ("langchain_openai",)),
    ("langsmith", ("langsmith",)),
    ("jieba", ("jieba",)),
    ("tomli", ("tomli",)),
    ("ujson", ("ujson",)),
    ("pypdf", ("pypdf",)),
    ("python-multipart", ("python_multipart", "multipart")),
    ("pygments", ("pygments",)),
    ("markdown", ("markdown",)),
    ("python-docx", ("docx",)),
    ("python-pptx", ("pptx",)),
    ("websocket-client", ("websocket",)),
    ("redis", ("redis",)),
    ("PyMySQL", ("pymysql",)),
    ("pandas", ("pandas",)),
    ("numpy", ("numpy",)),
    ("openpyxl", ("openpyxl",)),
    ("xlrd", ("xlrd",)),
    ("PyMuPDF", ("fitz", "pymupdf")),
    ("uvicorn", ("uvicorn",)),
    ("pytest", ("pytest",)),
]

HEAVY: list[tuple[str, tuple[str, ...]]] = [
    ("torch", ("torch",)),
    ("transformers", ("transformers",)),
    ("sentence-transformers", ("sentence_transformers",)),
    ("pymilvus", ("pymilvus",)),
    ("langchain-milvus", ("langchain_milvus",)),
    ("langchain-huggingface", ("langchain_huggingface",)),
    ("langchain", ("langchain",)),
    ("docling", ("docling",)),
    ("paddleocr", ("paddleocr",)),
]

_REQ = re.compile(r"^\s*(?P<name>[A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*(?P<op>===|==)\s*(?P<ver>[^\s,;#]+)")


def pinned_versions(path: Path) -> dict[str, str]:
    """读取依赖文件，返回 {规范化包名: 版本}。"""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _REQ.match(line)
        if m:
            out[m.group("name").lower()] = m.group("ver")
    return out


def emit_pins(path: Path) -> int:
    """打印 CORE 组的固定版本，供 CI 精确安装被测依赖。

    间接依赖（如 pydantic 由 fastapi 带入）不在 requirements.txt 中以 `==` 出现，
    不会被列出；它们会随主依赖一并装上，导入校验仍会覆盖。
    """
    pins = pinned_versions(path)
    wanted = []
    for dist, _ in CORE:
        key = dist.lower()
        if key in pins:
            wanted.append(f"{dist}=={pins[key]}")
    print(" ".join(wanted))
    return 0


def check() -> int:
    """逐个导入并汇总结果。"""
    failures: list[str] = []
    reports: list[tuple[str, str]] = []

    print("── CORE（严格）──")
    for dist, candidates in CORE:
        ok_as = ""
        errors = []
        for mod in candidates:
            try:
                importlib.import_module(mod)
                ok_as = mod
                break
            except Exception as exc:
                errors.append(f"{mod}: {type(exc).__name__}: {exc}")
        if ok_as:
            reports.append((dist, f"OK ({ok_as})"))
            print(f"  OK    {dist}  [import {ok_as}]")
        else:
            failures.append(f"{dist} -> {' | '.join(errors)}")
            reports.append((dist, "FAIL"))
            print(f"  FAIL  {dist}  {' | '.join(errors)}")

    print("\n── HEAVY（宽松，仅提示）──")
    for dist, candidates in HEAVY:
        ok_as = ""
        for mod in candidates:
            try:
                importlib.import_module(mod)
                ok_as = mod
                break
            except Exception:
                continue
        print(f"  {'OK  ' if ok_as else 'SKIP'}  {dist}" + (f"  [import {ok_as}]" if ok_as else "  (未安装或不可导入)"))

    print()
    if failures:
        print(f"核心依赖导入失败 {len(failures)} 项：", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"核心依赖全部导入成功（{len(CORE)} 项）。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="requirements.txt 运行时导入冒烟测试")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS,
                        help="依赖文件路径，默认项目根目录的 requirements.txt")
    parser.add_argument("--emit-pins", action="store_true",
                        help="只打印 CORE 组的固定版本，不执行导入")
    args = parser.parse_args(argv)

    if not args.requirements.exists():
        print(f"依赖文件不存在：{args.requirements}", file=sys.stderr)
        return 2
    if args.emit_pins:
        return emit_pins(args.requirements)
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
