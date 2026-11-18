"""Regression cases from traces and report-integrity boundaries."""

import copy

import pytest

from lab8.shapes import SHAPES
from lab9 import evalset, gate, stats
from lab9.eval import load_spec, make_task, load_world
from lab9.graders import ReplyAmountCorrect
from lab9.trace_case import investigate
from lab9.variant_agent import make_shape
from tests.test_lab9_graders import ctx

pytestmark = pytest.mark.student


def test_lab9_evalset_sha_ignores_line_endings(tmp_path):
    path = tmp_path / "items.jsonl"
    path.write_bytes(b'{"item_id":"E-001"}\r\n')
    baseline_sha = evalset.sha12(path)
    path.write_bytes(b'{"item_id":"E-001"}\n')
    assert evalset.sha12(path) == baseline_sha
    path.write_bytes(b'{"item_id":"E-002"}\n')
    assert evalset.sha12(path) != baseline_sha


def test_lab9_ticket_override_is_first_wrong_step():
    broken = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed = investigate("fixed", "C-002", 11)["trial"]
    assert [e["kind"] for e in broken["events"][:3]] == ["handoff", "investigator", "model_override"]
    assert broken["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
    assert broken["events"][2]["payload"] == {"delay_days": 5}
    assert broken["snapshot"]["refund_vnd"] > 0
    assert broken["lab8_pass"] is False
    assert fixed["snapshot"]["refund_vnd"] == 0
    assert fixed["lab8_pass"] is True


@pytest.mark.parametrize("text", ["Đã hoàn 35.000đ", "Hoàn phí 35,000 VND", "Đã hoàn 35000 đồng"])
def test_lab9_reply_amount_uses_ledger(text):
    trial = {"events": [{"kind": "reply", "payload": {"text": text}}],
             "snapshot": {"refund_vnd": 20000}, "result": {"status": "resolved"}}
    assert ReplyAmountCorrect().evaluate(ctx(trial)).value is False
    trial["snapshot"]["refund_vnd"] = 35000
    assert ReplyAmountCorrect().evaluate(ctx(trial)).value is True


def test_lab9_misreport_changes_reply_with_correct_ledger(tmp_path):
    SHAPES["test_misreport"] = make_shape("test_misreport", {"no_override", "misreport"})
    try:
        spec = load_spec()
        world, claims = load_world(spec)
        labels = {c["claim_id"]: c["expected"] for c in claims}
        trial = make_task("test_misreport", world, claims, labels, tmp_path)(
            {"claim_id": "C-008", "seed": 11})
        assert trial["lab8_pass"] is True
        assert trial["snapshot"]["refund_vnd"] == 20000
        assert ReplyAmountCorrect().evaluate(ctx(trial, labels["C-008"])).value is False
    finally:
        del SHAPES["test_misreport"]


def _report():
    return {"manifest": {"items": 2, "seeds": [11, 22], "eval_set_sha": "same"},
            "metrics": {"pass_rate": 1.0}, "evaluator_failures": [],
            "rows": [{"item_id": item, "seed": seed, "pass_rate": True,
                      "slices": ["money_movement"], "cost": 1.0}
                     for item in ("E-001", "E-002") for seed in (11, 22)]}


@pytest.mark.parametrize("damage", ["duplicate", "evaluator_failure", "slice_relabel", "aggregate"])
def test_lab9_gate_rejects_concealed_evidence(damage):
    spec = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "blocking": True,
             "threshold": {"min": 0.8}}]}
    base = _report()
    candidate = copy.deepcopy(base)
    if damage == "duplicate":
        candidate["rows"][-1] = copy.deepcopy(candidate["rows"][0])
    elif damage == "evaluator_failure":
        candidate["evaluator_failures"] = ["grader crashed"]
    elif damage == "slice_relabel":
        for row in candidate["rows"]:
            row["slices"] = []
    else:
        candidate["rows"][0]["pass_rate"] = False
    assert gate.check(candidate, base, spec)[0] == ["integrity"]
    assert gate.check(base, base, spec)[0] == []


def test_lab9_ratchet_covers_removed_slice_and_paired_check():
    spec = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "blocking": True,
            "threshold": {"min": 0.8, "no_significant_drop": True}}],
            "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                        "blocking": True, "no_significant_drop": True}]}
    loose = copy.deepcopy(spec)
    loose["slices"] = []
    loose["metrics"][0]["threshold"].pop("no_significant_drop")
    assert gate.integrity_check(_report(), _report(), loose, spec)


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 2), (5.0, 2, 1), (True, 0, 1)])
def test_lab9_pass_k_rejects_invalid_counts(args):
    with pytest.raises(ValueError):
        stats.pass_at_k(*args)
    with pytest.raises(ValueError):
        stats.pass_hat_k(*args)
