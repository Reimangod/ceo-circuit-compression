import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_readme_assets import build, generated_files
from check_repository import check, check_markdown, check_svg, headings


def test_repository_checks_without_running_molecular_code():
    result = check()
    assert result["status"] == "PASS", result["errors"]
    assert result["new_molecular_evaluations"] == 0


def test_local_links_and_heading_anchors(tmp_path):
    (tmp_path / "guide.md").write_text("# First heading\n\n## Next step\n")
    page = tmp_path / "README.md"
    page.write_text("[Guide](guide.md#next-step)\n[Website](https://example.org)\n")
    assert not check_markdown(tmp_path, [page])


@pytest.mark.parametrize("target", ["missing.md", "guide.md#absent", "../outside.md"])
def test_broken_or_escaping_links_are_rejected(tmp_path, target):
    (tmp_path / "guide.md").write_text("# Existing\n")
    page = tmp_path / "README.md"
    page.write_text(f"[Broken]({target})\n")
    assert check_markdown(tmp_path, [page])


def test_english_guides_allow_scientific_unicode(tmp_path):
    page = tmp_path / "README.md"
    page.write_text("# BeH₂ at 1.50 Å\nEnergy difference: −0.07 mHa.\n")
    assert not check_markdown(tmp_path, [page])
    page.write_text("# Non-English guide\n" + chr(0x65E5))
    assert check_markdown(tmp_path, [page])


def test_heading_duplicates_have_distinct_github_anchors():
    assert headings("# Same\n## Same\n# Same\n") == {"same", "same-1", "same-2"}


def test_overview_assets_match_saved_values_and_are_deterministic():
    assert generated_files() == generated_files()
    assert build(check=True)["status"] == "PASS"
    selection = json.loads((ROOT / "data/metadata/report-selection.json").read_text())
    pair = next(r for r in selection["current"] if r["molecule"] == "LiH" and r["distance_A"] == 1.5)
    assert [pair[k]["cnot"] for k in ("ceo", "common_resources", "child")] == [112, 100, 65]


def test_stale_generated_document_is_rejected(tmp_path):
    source = ROOT / "data/metadata/report-selection.json"
    destination = tmp_path / "data/metadata/report-selection.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    build(tmp_path)
    (tmp_path / "docs/RESULTS.md").write_text("out of date\n")
    with pytest.raises(ValueError, match="Stale generated documentation"):
        build(tmp_path, check=True)


def test_svg_assets_have_accessible_english_labels():
    for path in (ROOT / "docs/assets").glob("*.svg"):
        assert not check_svg(path)


def test_svg_external_resource_is_rejected(tmp_path):
    path = tmp_path / "bad.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                    '<title>Example</title><desc>Example</desc>'
                    '<image href="https://example.org/pixel.png"/></svg>')
    assert check_svg(path)


def test_workflow_actions_are_pinned_and_permissions_are_read_only():
    text = (ROOT / ".github/workflows/verify.yml").read_text()
    import re
    actions = re.findall(r"uses:\s+(\S+)", text)
    assert actions
    assert all(re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", value) for value in actions)
    assert "contents: read" in text
    assert "pull_request_target" not in text
    assert "contents: write" not in text
    assert "uv sync --frozen" in text
