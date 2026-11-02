"""Check maintained documentation and frozen identities without release data."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
LINK = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
LOCAL_GUIDANCE = {"AGENTS.MD", "AGENT.MD", "CLAUDE.MD"}
LOCAL_FOLDERS = {".codex", ".agents", ".claude", ".idea", ".vscode"}


def distribution_errors(names):
    errors = []
    for name in names:
        path = PurePosixPath(name)
        if path.name.upper() in LOCAL_GUIDANCE or any(part.lower() in LOCAL_FOLDERS for part in path.parts):
            errors.append(f"Local assistant/editor configuration is not distributed: {name}")
    return errors


def markdown_paths(root):
    root = Path(root)
    return sorted(set(root.glob("*.md")) | set((root / "docs").rglob("*.md")) |
                  set((root / ".github").rglob("*.md")))


def headings(text):
    result, counts = set(), Counter()
    for line in text.splitlines():
        if not re.match(r"^#{1,6} ", line):
            continue
        text = re.sub(r"^#+\s+", "", line).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
        number = counts[slug]
        counts[slug] += 1
        result.add(slug if number == 0 else f"{slug}-{number}")
    return result


def check_markdown(root, paths):
    root = Path(root).resolve()
    errors = []
    for path in paths:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if CJK.search(text):
            errors.append(f"Maintained guide must use English: {path.relative_to(root)}")
        prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        for target in LINK.findall(prose):
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or parsed.netloc:
                continue
            dest = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path.resolve()
            if not dest.is_relative_to(root):
                errors.append(f"Link escapes the repository: {target}")
            elif not dest.exists():
                errors.append(f"Missing local link in {path.relative_to(root)}: {target}")
            elif parsed.fragment and dest.suffix == ".md":
                if unquote(parsed.fragment) not in headings(dest.read_text(encoding="utf-8")):
                    errors.append(f"Missing heading anchor in {path.relative_to(root)}: {target}")
    return errors


def check_svg(path):
    errors = []
    root = ET.parse(path).getroot()
    namespace = "{http://www.w3.org/2000/svg}"
    if root.tag != namespace + "svg" or not root.get("viewBox"):
        errors.append(f"SVG needs a viewBox: {path}")
    for name in ("title", "desc"):
        if root.find(namespace + name) is None:
            errors.append(f"SVG needs accessible {name}: {path}")
    if CJK.search("".join(root.itertext())):
        errors.append(f"Overview SVG must use English: {path}")
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] in ("script", "foreignObject"):
            errors.append(f"Active SVG content is not supported: {path}")
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith("#"):
                errors.append(f"External SVG resource is not supported: {path}")
    return errors


def check(root=ROOT):
    root = Path(root).resolve()
    errors = check_markdown(root, markdown_paths(root))
    for path in (root / "docs/assets").glob("*.svg"):
        errors.extend(check_svg(path))
    syntax_count = 0
    for folder in ("tools", "tests"):
        for path in (root / folder).glob("*.py"):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                syntax_count += 1
            except SyntaxError as exc:
                errors.append(f"Python syntax: {path.relative_to(root)}: {exc}")
    code = json.loads((root / "data/metadata/policy-files.json").read_text())
    for entry in code:
        path = root / entry["file"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append(f"Frozen implementation hash mismatch: {entry['file']}")
    census = json.loads((root / "data/metadata/census.json").read_text())
    selected = json.loads((root / "data/metadata/report-selection.json").read_text())
    if len(census["cases"]) != 41 or len(selected["current"]) != 22:
        errors.append("Scope mismatch: expected 41 historical / 22 current conditions")
    try:
        from build_readme_assets import build
        build(root, check=True)
    except (ValueError, AssertionError) as exc:
        errors.append(str(exc) or "Generated documentation does not match the recorded selection")
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    ).decode().split("\0")
    for name in tracked:
        if not name or not (root / name).is_file():
            continue
        errors.extend(distribution_errors([name]))
        if (root / name).stat().st_size > 20 * 1024 * 1024:
            errors.append(f"Large Git payload; use a separate data asset: {name}")
        if name.startswith(("data/raw/", ".venv/", "ci-results/", "execution/")):
            errors.append(f"Generated or private payload is tracked: {name}")
    return dict(status="FAIL" if errors else "PASS", errors=errors,
                maintained_guides=len(markdown_paths(root)), frozen_files=len(code),
                parsed_python_files=syntax_count, current_conditions=22,
                historical_conditions=41, new_molecular_evaluations=0,
                scope="checkout-only; raw object verification is a separate command")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
