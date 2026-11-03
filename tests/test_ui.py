"""Renderer structure/text under the kit interface; real-browser layout is not exercised."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

from contract import LineInput, MateInput
from plugin import check_mate_line, find_forced_mate

ROOT = Path(__file__).resolve().parents[1]
KIT = """
export const h = (tag, attrs = {}, ...children) => ({tag, attrs, children});
export const statusPill = (text) => h("span", {text});
export const disclosure = (options, ...children) => h("details", {}, options.summary, children);
export const dataTable = ({columns, rows}) => ({element: h("table", {}, rows.map(row => columns.map(column => row[column.key])))});
"""
DRAW = """
import {readFileSync} from "node:fs";
import renderers from "./renderers.mjs";
const sample = JSON.parse(readFileSync("sample.json", "utf8"));
function text(node) {
  if (node == null || node === false) return "";
  if (Array.isArray(node)) return node.map(text).join(" ");
  if (typeof node !== "object") return String(node);
  return (node.attrs?.text ?? "") + " " + text(node.children);
}
console.log(text(renderers[sample.outputClass](sample.value, {verdict:sample.verdict})));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="renderer check needs Node")
@pytest.mark.parametrize(
    "name,valid,words",
    [
        ("mate-one", True, "Play g6g7"),
        ("mate-three", True, "Forced mate within 3"),
        ("two-not-one", True, "No forced mate within 1"),
        ("line-mate", True, "Legal line ending in checkmate"),
        ("line-illegal", True, "Illegal move at step 3"),
        ("mate-one", False, "Verification failed"),
    ],
)
def test_result_card(name, valid, words, tmp_path):
    raw = json.loads((ROOT / "tests/cases" / f"{name}.input.json").read_text())
    is_mate = "max_moves" in raw
    given = build_output(raw, MateInput if is_mate else LineInput)
    made = (find_forced_mate if is_mate else check_mate_line)(given, tmp_path)
    sample = {
        "outputClass": "MateOutput" if is_mate else "LineOutput",
        "value": plain_output(made),
        "verdict": {"valid": valid, "message": "bad certificate" if not valid else "checked"},
    }
    source = (ROOT / "ui/renderers.js").read_text().replace("./kit/components.js", "./components.mjs")
    for filename, content in [
        ("renderers.mjs", source),
        ("components.mjs", KIT),
        ("draw.mjs", DRAW),
        ("sample.json", json.dumps(sample)),
    ]:
        (tmp_path / filename).write_text(content)
    result = subprocess.run(["node", "draw.mjs"], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert words in result.stdout
    if valid:
        assert "move-count draws are excluded" in result.stdout and "a8" in result.stdout
    else:
        assert "Play g6g7" not in result.stdout
