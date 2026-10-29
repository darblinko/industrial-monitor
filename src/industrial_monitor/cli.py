"""Command-line entry point: `industrial-monitor <command>`."""

import argparse
import asyncio
import contextlib
import json
import sys
import threading
from pathlib import Path

from industrial_monitor.demo import DEMO_WINDOWS, publish_demo, run_demo
from industrial_monitor.detection_eval import (
    MACHINES_PER_FAULT,
    TEST_WINDOWS,
    run_detection_evaluation,
)
from industrial_monitor.machines import FLEET
from industrial_monitor.monitor import MonitorConfig, PlantMonitor, load_snapshot, save_snapshot
from industrial_monitor.settings import Settings

DEFAULT_STATE_FILE = Path("results/scratch/plant-state.json")
DEMO_STATE_FILE = Path("eval/plant-state.json")
CORPUS_DIR = Path("corpus")
GOLDEN_FILE = Path("eval/golden.jsonl")


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {path}")


def _format_states(statuses: list[dict]) -> list[str]:
    header = (
        f"{'machine':<8} {'state':<9} {'hypothesis':<18} {'since':>5} {'vel_mm_s':>8} {'temp_c':>6}"
    )
    rows = [header]
    for status in statuses:
        since = status["alarm_since_window"]
        rows.append(
            f"{status['machine_id']:<8} {status['state']:<9} {status['hypothesis'] or '-':<18} "
            f"{'-' if since is None else since:>5} {status['velocity_rms_mm_s']:>8.2f} "
            f"{status['temperature_c']:>6.1f}"
        )
    return rows


def cmd_evaluate_detector(args: argparse.Namespace, settings: Settings) -> int:
    result = run_detection_evaluation(args.machines_per_fault, args.test_windows)
    _write_json(args.output, result)
    calibrated = result["modes"]["two_of_three"]["evaluation"]
    print(
        f"threshold {result['calibration']['threshold']}: "
        f"false-alarm rate {calibrated['false_alarm_rate']:.4f}, "
        f"detection rate {calibrated['detection_rate']['all']:.4f}"
    )
    return 0


def cmd_demo(args: argparse.Namespace, settings: Settings) -> int:
    monitor = run_demo(windows=args.windows, threshold=settings.threshold)
    print("\n".join(_format_states(monitor.snapshot())))
    if args.save:
        save_snapshot(args.save, monitor.snapshot())
        print(f"wrote {args.save}")
    return 0


def _assistant(args: argparse.Namespace, settings: Settings):
    """(model, toolbox), or None after printing why the model is unavailable."""
    from industrial_monitor.assistant.corpus import BM25Index, load_corpus
    from industrial_monitor.assistant.fake_model import FakeModel
    from industrial_monitor.assistant.tools import Toolbox

    if args.model == "claude":
        if not settings.anthropic_api_key:
            print("--model claude needs ANTHROPIC_API_KEY in the environment", file=sys.stderr)
            return None
        from industrial_monitor.assistant.claude_model import ClaudeModel

        model = ClaudeModel(model=settings.claude_model)
    else:
        model = FakeModel()
    toolbox = Toolbox(load_snapshot(args.state_file), BM25Index(load_corpus(CORPUS_DIR)))
    return model, toolbox


def cmd_ask(args: argparse.Namespace, settings: Settings) -> int:
    from industrial_monitor.assistant.agent import run_agent

    assistant = _assistant(args, settings)
    if assistant is None:
        return 2
    run = run_agent(args.question, *assistant)
    print(run.answer or f"(no answer: {run.stop_reason})")
    print(f"\ntools: {', '.join(call.name for call in run.tool_calls) or 'none'}")
    return 0


def cmd_evaluate_assistant(args: argparse.Namespace, settings: Settings) -> int:
    from industrial_monitor.assistant.evaluation import evaluate, load_golden

    assistant = _assistant(args, settings)
    if assistant is None:
        return 2
    result = evaluate(*assistant, load_golden(GOLDEN_FILE))
    output = args.output or Path(f"results/assistant-eval-{args.model}.json")
    _write_json(output, result)
    for metric, value in result["summary"].items():
        print(f"{metric:<24} {value if not isinstance(value, float) else round(value, 3)}")
    return 0


def _mqtt_bus(settings: Settings):
    from industrial_monitor.mqtt_bus import MqttBus

    return MqttBus(settings.mqtt_host, settings.mqtt_port)


def cmd_simulate(args: argparse.Namespace, settings: Settings) -> int:
    with _mqtt_bus(settings) as bus:
        publish_demo(bus, args.windows, args.interval, site=settings.site)
    print(
        f"published {args.windows} windows for {len(FLEET)} machines "
        f"to {settings.mqtt_host}:{settings.mqtt_port}"
    )
    return 0


def _transition_printer():
    last_state: dict[str, str] = {}

    def report(status: dict) -> None:
        machine, state = status["machine_id"], status["state"]
        previous = last_state.get(machine)
        last_state[machine] = state
        if previous is not None and previous != state:
            detail = f" ({status['hypothesis']})" if status["hypothesis"] else ""
            print(f"window {status['window']}: {machine} {previous} to {state}{detail}", flush=True)

    return report


def cmd_monitor(args: argparse.Namespace, settings: Settings) -> int:
    with _mqtt_bus(settings) as bus:
        config = MonitorConfig(site=settings.site, threshold=settings.threshold)
        monitor = PlantMonitor(bus, FLEET, config)
        report = _transition_printer()

        def on_anomaly(topic: str, payload: bytes) -> None:
            report(json.loads(payload))
            save_snapshot(args.state_file, monitor.snapshot())

        bus.subscribe(f"plant/{settings.site}/+/anomaly", on_anomaly)
        bus.wait_for_subscriptions()
        print(f"monitoring plant/{settings.site}/#, state in {args.state_file}", flush=True)
        with contextlib.suppress(KeyboardInterrupt):
            threading.Event().wait(args.duration)
    print(f"rejected messages: {dict(monitor.rejected) or 'none'}")
    return 0


def _tag_mapping(text: str) -> tuple[str, str]:
    mac, separator, machine = text.partition("=")
    if not separator or not machine:
        raise argparse.ArgumentTypeError(f"expected MAC=machine-id, got {text!r}")
    return mac.upper(), machine


def cmd_scan_ble(args: argparse.Namespace, settings: Settings) -> int:
    try:
        import bleak  # noqa: F401
    except ImportError:
        print("BLE scanning needs the optional extra: uv sync --extra ble", file=sys.stderr)
        return 2
    from industrial_monitor.ble import scan

    with _mqtt_bus(settings) as bus:
        count = asyncio.run(scan(bus, settings.site, args.duration, dict(args.map)))
    print(f"published {count} RAWv2 advertisements")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="industrial-monitor", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser(
        "evaluate-detector", help="measure detection and false-alarm rates on labeled windows"
    )
    evaluate.add_argument("--machines-per-fault", type=int, default=MACHINES_PER_FAULT)
    evaluate.add_argument("--test-windows", type=int, default=TEST_WINDOWS)
    evaluate.add_argument("--output", type=Path, default=Path("results/detection.json"))
    evaluate.set_defaults(handler=cmd_evaluate_detector)

    demo = commands.add_parser("demo", help="replay the demo plant in process, print states")
    demo.add_argument("--windows", type=int, default=DEMO_WINDOWS)
    demo.add_argument("--save", type=Path, help="write the final plant state to this file")
    demo.set_defaults(handler=cmd_demo)

    for name, handler, help_text in (
        ("ask", cmd_ask, "ask the maintenance assistant one question"),
        ("evaluate-assistant", cmd_evaluate_assistant, "score the assistant on eval/golden.jsonl"),
    ):
        command = commands.add_parser(name, help=help_text)
        if name == "ask":
            command.add_argument("question")
        else:
            command.add_argument("--output", type=Path)
        command.add_argument("--model", choices=("fake", "claude"), default="fake")
        command.add_argument("--state-file", type=Path, default=DEMO_STATE_FILE)
        command.set_defaults(handler=handler)

    simulate = commands.add_parser("simulate", help="publish the demo plant to the MQTT broker")
    simulate.add_argument("--windows", type=int, default=DEMO_WINDOWS)
    simulate.add_argument("--interval", type=float, default=0.5, help="seconds between windows")
    simulate.set_defaults(handler=cmd_simulate)

    live = commands.add_parser("monitor", help="run the detector on messages from the broker")
    live.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    live.add_argument("--duration", type=float, default=None, help="seconds; default until Ctrl-C")
    live.set_defaults(handler=cmd_monitor)

    ble = commands.add_parser("scan-ble", help="publish RAWv2 from nearby Ruuvi tags (optional)")
    ble.add_argument("--duration", type=float, default=30.0, help="seconds to scan")
    ble.add_argument("--map", type=_tag_mapping, action="append", default=[], help="MAC=machine-id")
    ble.set_defaults(handler=cmd_scan_ble)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args, Settings.from_env())


if __name__ == "__main__":
    sys.exit(main())
