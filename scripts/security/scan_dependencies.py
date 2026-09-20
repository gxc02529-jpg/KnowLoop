# -*- coding: utf-8 -*-
"""扫描 requirements.txt 中固定版本的依赖，报告已知漏洞（数据源：OSV）。

为什么需要这个脚本：
  本仓库的公开回归测试只安装一份手挑依赖子集，不执行 requirements.txt。
  这意味着 requirements.txt 的任何变更都不会被测试发现。本脚本补上这块可观测性：
  它把「当前固定的这批版本存在哪些已知漏洞」变成可复现、可进 CI 的输出。

数据源选择：
  OSV（https://osv.dev）由 Google 维护，聚合 GitHub Advisory / PyPA / NVD，
  对 PyPI 生态的覆盖与 GitHub Dependabot 一致，且无需鉴权。

用法：
    python scripts/security/scan_dependencies.py
    python scripts/security/scan_dependencies.py --json reports/security/osv.json
    python scripts/security/scan_dependencies.py --fail-on HIGH   # 供 CI 卡口使用

退出码：
    0  正常完成（未触发 --fail-on 阈值）
    1  达到 --fail-on 指定的严重度阈值
    2  参数或读取错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OSV_ENDPOINT = "https://api.osv.dev/v1/query"
ECOSYSTEM = "PyPI"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1, "": 0}

# 形如 name、name[extra]==1.2.3、name>=1.0,<2.0
_REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*(?P<op>===|==|~=|>=|<=|>|<)?\s*(?P<ver>[^\s,;#]+)?"
)


def parse_requirements(path: Path) -> list[tuple[str, str | None]]:
    """解析依赖文件，返回 (包名, 精确版本或 None)。

    只识别精确固定（`==` / `===`）的版本；区间约束无法判定具体命中版本，
    此时返回 None，调用方按“该包存在已知漏洞”处理。

    参数：
        path: requirements 文件路径。

    返回：
        (包名, 版本) 列表。

    异常：
        FileNotFoundError: 文件不存在。
    """
    items: list[tuple[str, str | None]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            # 跳过注释、空行与 --index-url / -r 之类的选项行
            continue
        line = line.split(";")[0].strip()
        m = _REQ.match(line)
        if not m:
            continue
        name = m.group("name")
        ver = m.group("ver") if m.group("op") in ("==", "===") else None
        items.append((name, ver))
    return items


def query_osv(package: str, version: str | None, *, timeout: int = 30,
              retries: int = 3) -> list[dict]:
    """查询单个包的漏洞列表。

    参数：
        package: PyPI 包名。
        version: 精确版本；为 None 时返回该包的全部已知漏洞。
        timeout: 单次请求超时秒数。
        retries: 失败重试次数。

    返回：
        OSV 漏洞记录列表。
    """
    payload: dict = {"package": {"name": package, "ecosystem": ECOSYSTEM}}
    if version:
        payload["version"] = version
    data = json.dumps(payload).encode("utf-8")

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                OSV_ENDPOINT, data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8")).get("vulns", []) or []
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            last_error = exc
        except Exception as exc:  # 网络抖动不值得让整个扫描失败
            last_error = exc
        time.sleep(1 + attempt)
    raise RuntimeError(f"OSV 查询失败：{package} {version or ''} -> {last_error}")


def severity_of(vuln: dict) -> str:
    """从 OSV 记录里取严重度。

    GHSA 来源的记录带 database_specific.severity；PYSEC 来源的常常为空，
    此时退回解析 CVSS 向量，仍取不到则返回空串（表示未知）。

    参数：
        vuln: OSV 漏洞记录。

    返回：
        严重度字符串（如 HIGH），未知时为空串。
    """
    db = vuln.get("database_specific") or {}
    if db.get("severity"):
        return str(db["severity"]).upper()
    for entry in vuln.get("severity") or []:
        vector = str(entry.get("score") or "")
        if vector.startswith("CVSS:"):
            for part in vector.split("/"):
                if part.startswith("S:"):
                    return part[2:].upper()
    return ""


def fixed_version(vuln: dict, package: str) -> str | None:
    """取出修复版本。

    参数：
        vuln: OSV 漏洞记录。
        package: 目标包名，用于过滤 affected 条目。

    返回：
        修复版本字符串；未标注版本号（例如只给 commit）时返回 None。
    """
    for affected in vuln.get("affected") or []:
        name = ((affected.get("package") or {}).get("name") or "").lower()
        if name and name != package.lower():
            continue
        for rng in affected.get("ranges") or []:
            for event in rng.get("events") or []:
                fixed = event.get("fixed")
                if fixed and re.match(r"^\d", str(fixed)):
                    return str(fixed)
    return None


def version_key(version: str) -> tuple:
    """把版本号转成可比较的元组，用于挑选“能清空全部已知漏洞”的目标版本。"""
    cleaned = re.sub(r"^[v=<>!\s]+", "", version.split("+")[0])
    parts = [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", cleaned)[:4]]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


def scan(requirements: Path) -> dict:
    """扫描依赖文件并聚合结果。

    按包聚合而不是逐条漏洞罗列：单个包常有几十条告警（例如 pypdf），
    逐条列没有可执行性；这里给出“升到哪个版本能一次清空该包全部已知漏洞”。

    参数：
        requirements: 依赖文件路径。

    返回：
        {"包名": {"current", "target", "severity", "advisories": [...]}} 形式的字典。
    """
    deps = parse_requirements(requirements)
    result: dict[str, dict] = {}
    for name, version in deps:
        try:
            vulns = query_osv(name, version)
        except RuntimeError as exc:
            print(f"  ! {name}: {exc}", file=sys.stderr)
            continue
        if not vulns:
            continue
        fixes, severities, records = [], [], []
        for vuln in vulns:
            sev = severity_of(vuln)
            if sev:
                severities.append(sev)
            fixed = fixed_version(vuln, name)
            if fixed:
                fixes.append(fixed)
            records.append({
                "id": vuln.get("id"),
                "aliases": vuln.get("aliases") or [],
                "severity": sev,
                "fixed": fixed,
                "summary": (vuln.get("summary") or "").strip(),
            })
        target = max(fixes, key=version_key) if fixes else None
        if target and version and version_key(target) <= version_key(version):
            # 所有相关漏洞的修复版本都不高于当前固定版本 → 已被覆盖，无需处置
            continue
        result[name] = {
            "current": version,
            "target": target,
            "severity": max(severities, key=lambda s: SEVERITY_RANK.get(s, 0), default=""),
            "advisories": sorted(records, key=lambda r: -SEVERITY_RANK.get(r["severity"], 0)),
        }
    return result


def render(result: dict) -> str:
    """把扫描结果渲染成可读表格。"""
    if not result:
        return "未发现已知漏洞。"
    lines = ["| 包 | 当前 | 升到 | 严重度 | 告警数 |", "| --- | --- | --- | --- | --- |"]
    ordered = sorted(
        result.items(),
        key=lambda kv: (-SEVERITY_RANK.get(kv[1]["severity"], 0), -len(kv[1]["advisories"]), kv[0]),
    )
    for name, info in ordered:
        if info.get("target"):
            target = f">= {info['target']}"
        elif info["current"]:
            target = "已覆盖"
        else:
            target = "需人工确认"
        lines.append("| `{}` | {} | {} | {} | {} |".format(
            name, info["current"] or "区间", target,
            info["severity"] or "未知", len(info["advisories"])))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 OSV 扫描固定依赖的已知漏洞")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS,
                        help="依赖文件路径，默认 requirements.txt")
    parser.add_argument("--json", type=Path, default=None,
                        help="把结构化结果写入指定 JSON 文件")
    parser.add_argument("--fail-on", choices=["LOW", "MODERATE", "MEDIUM", "HIGH", "CRITICAL"],
                        default=None,
                        help="达到该严重度时以退出码 1 结束，用于 CI 卡口")
    args = parser.parse_args(argv)

    if not args.requirements.exists():
        print(f"依赖文件不存在：{args.requirements}", file=sys.stderr)
        return 2

    result = scan(args.requirements)
    print(render(result))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结构化结果：{args.json}")

    if args.fail_on:
        threshold = SEVERITY_RANK[args.fail_on]
        hits = [n for n, i in result.items() if SEVERITY_RANK.get(i["severity"], 0) >= threshold]
        if hits:
            print(f"\n达到 {args.fail_on} 及以上的依赖：{', '.join(sorted(hits))}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
