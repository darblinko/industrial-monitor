# Chart tooling

`svgchart.py` renders the README figures in `docs/figures` from `docs/data.json`. `docs/charts.js` renders the same data as interactive charts on the landing page. Both files are copied unchanged from a chart kit shared by several repositories, which is why this directory is excluded from ruff.

## Regenerate the figures

```bash
uv run industrial-monitor export-landing                        # writes docs/data.json
python3 tools/publish-kit/svgchart.py docs/data.json docs/figures
```

The second command writes `<name>-light.svg` and `<name>-dark.svg` for every chart and prints a Markdown snippet per chart: a `<picture>` element and a collapsed data table, as used in the README. It needs only the Python standard library. `tests/test_figures.py` fails when the committed SVG files differ from what `svgchart.py` renders from the committed `docs/data.json`.

## docs/data.json schema

```json
{
  "meta": {"repo": "industrial-monitor", "revision": "<commit>", "measured": "<YYYY-MM-DD>"},
  "charts": [
    {"name": "example", "type": "hbar", "title": "Example rate per class",
     "subtitle": "Illustrative values", "source": "results/example.json",
     "alt": "Class A 50%, class B 75%.",
     "format": "percent", "max": 1, "threshold": {"value": 0.6, "label": "target 60%"},
     "data": [{"label": "Class A", "value": 0.5, "status": "fail"},
              {"label": "Class B", "value": 0.75, "status": "pass"}]}
  ]
}
```

Every chart has `name`, `type`, `title`, `subtitle`, `source` (the file or command its numbers come from) and `alt` (the text alternative).

| type | Required fields | Use |
|---|---|---|
| hbar | data: [{label, value, status?, note?}]; optional max, threshold {value, label} | Per-class or per-rule comparisons. status is "pass" or "fail" and prints beside the bar. |
| columns | categories: [...], series: [{name, values}] (1 to 4 series) | Values per category |
| line | x: [...], series: [{name, values}] (1 to 4 series; null for a gap; the last value must be a number); optional min, max | Values along an ordered axis |
| stats | tiles: [{label, value (preformatted string), note?}] | Headline figures, at most 4 per row |

`format` is one of `percent` (values are fractions, 0.86 prints 86%), `number` (default), `decimal2` or `decimal3`.
