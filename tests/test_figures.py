import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs" / "data.json").read_text())


def _svgchart():
    spec = importlib.util.spec_from_file_location(
        "svgchart", ROOT / "tools" / "publish-kit" / "svgchart.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_committed_figures_match_the_committed_chart_data(mode):
    svgchart = _svgchart()
    for chart in DATA["charts"]:
        figure = ROOT / "docs" / "figures" / f"{chart['name']}-{mode}.svg"
        assert figure.read_text() == svgchart.render_svg(chart, mode), figure.name


def test_every_figure_file_belongs_to_a_chart():
    names = {chart["name"] for chart in DATA["charts"]}
    for figure in (ROOT / "docs" / "figures").glob("*.svg"):
        assert figure.stem.rsplit("-", 1)[0] in names, figure.name
