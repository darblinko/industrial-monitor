import re
from pathlib import Path

from industrial_monitor.assistant.agent import DECLINE, run_agent
from industrial_monitor.assistant.corpus import BM25Index, load_corpus
from industrial_monitor.assistant.fake_model import FakeModel
from industrial_monitor.assistant.tools import Toolbox

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def status(machine_id, equipment, state, hypothesis=None, channel="amp_1x_g", z=0.5):
    return {
        "machine_id": machine_id,
        "equipment": equipment,
        "state": state,
        "hypothesis": hypothesis,
        "alarm_since_window": 71 if state == "alarm" else None,
        "channel_z": {"amp_1x_g": 0.1, "bearing_envelope": 0.2, channel: z},
        "velocity_rms_mm_s": 2.3,
        "temperature_c": 41.9,
        "bpfo_hz": 83.53,
    }


STATUSES = [
    status("pump-3", "RP-1 centrifugal pump", "alarm", "bearing_wear", "bearing_envelope", 19.2),
    status("pump-1", "RP-1 centrifugal pump", "normal"),
    status("fan-2", "RF-1 centrifugal fan", "alarm", "imbalance", "amp_1x_g", 10.7),
]


def ask(question):
    return run_agent(question, FakeModel(), Toolbox(STATUSES, BM25Index(load_corpus(CORPUS))))


def test_alarm_question_reads_state_then_searches_and_cites_both():
    run = ask("Why is pump 3 alarming and what do I check?")
    assert [call.name for call in run.tool_calls] == ["get_machine_status", "search_manual"]
    assert "[status:pump-3]" in run.answer
    assert "[RP-3.2]" in run.answer
    assert "bearing" in run.answer.lower()
    sentences = re.split(r"(?<=\]\.)\s+", run.answer)
    assert all(re.search(r"\[[^\]]+\]\.$", sentence) for sentence in sentences)


def test_healthy_machine_is_answered_from_state_alone():
    run = ask("Is pump 1 running normally?")
    assert [call.name for call in run.tool_calls] == ["get_machine_status"]
    assert "normal" in run.answer
    assert "[status:pump-1]" in run.answer


def test_alarm_list_names_every_alarming_machine():
    run = ask("Which machines are alarming right now?")
    assert [call.name for call in run.tool_calls] == ["list_alarms"]
    assert "[status:pump-3]" in run.answer
    assert "[status:fan-2]" in run.answer
    assert "pump-1" not in run.answer


def test_manual_question_cites_the_matching_passage():
    run = ask("What is the vibration trip limit for the RP-1 pump?")
    assert "[RP-2.1]" in run.answer
    assert "7.1" in run.answer


def test_question_outside_the_manual_is_declined():
    assert ask("What torque is specified for the RP-1 impeller nut?").answer == DECLINE


def test_passages_for_other_equipment_are_not_cited():
    run = ask("Fan 2 has an alarm. What does it mean and can it keep running?")
    assert "[RF-4.1]" in run.answer
    assert "[RP-" not in run.answer
