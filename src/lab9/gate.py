"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    identities = []
    slice_maps = []
    for name, report in (("PR", pr), ("baseline", base)):
        manifest = report.get("manifest", {})
        rows = report.get("rows")
        metrics = report.get("metrics")
        seeds = manifest.get("seeds", [])
        items = manifest.get("items")
        if (not isinstance(rows, list) or not isinstance(metrics, dict)
                or not isinstance(items, int) or isinstance(items, bool) or items < 1
                or not isinstance(seeds, list) or not seeds
                or any(not isinstance(s, int) or isinstance(s, bool) for s in seeds)
                or len(set(seeds)) != len(seeds)):
            problems.append(f"{name}: invalid report schema")
            continue
        if report.get("evaluator_failures") != []:
            problems.append(f"{name}: evaluator failures or missing failure manifest")
        if len(rows) != items * len(seeds):
            problems.append(f"{name}: row count differs from manifest")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()):
            problems.append(f"{name}: nonfinite or missing aggregate metric")
        if any(m["id"] not in metrics for m in spec["metrics"]):
            problems.append(f"{name}: missing spec metric")
        invalid_rows = False
        pairs, tags = [], {}
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str)
                    or not isinstance(row.get("seed"), int) or isinstance(row.get("seed"), bool)):
                invalid_rows = True
                continue
            item, seed = row["item_id"], row["seed"]
            pairs.append((item, seed))
            slices = row.get("slices", [])
            if (not isinstance(slices, list) or any(not isinstance(tag, str) for tag in slices)
                    or len(set(slices)) != len(slices)):
                invalid_rows = True
                continue
            current = frozenset(slices)
            if item in tags and tags[item] != current:
                invalid_rows = True
            tags[item] = current
            if any(not isinstance(row.get(mid), (bool, int, float))
                   or not math.isfinite(row[mid]) or row[mid] not in (0, 1) for mid in graded):
                invalid_rows = True
            cost = row.get("cost", 0)
            if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                invalid_rows = True
        if invalid_rows:
            problems.append(f"{name}: malformed row, grader value, cost or slice tags")
        coverage = Counter(pairs)
        expected = {(item, seed) for item in tags for seed in seeds}
        if len(tags) != items or set(coverage) != expected or any(n != 1 for n in coverage.values()):
            problems.append(f"{name}: missing, duplicate or unexpected item/seed rows")
        identities.append(set(pairs))
        slice_maps.append(tags)
        if spec.get("seeds") is not None and set(seeds) != set(spec["seeds"]):
            problems.append(f"{name}: seeds differ from metric spec")
        if not invalid_rows and rows:
            recomputed = aggregate([{**r, "cost": r.get("cost", 0)} for r in rows], graded,
                                   k_values=spec.get("pass_k", []))
            for mid, expected_value in recomputed.items():
                # Recompute supplied summaries, including optional tracking metrics.
                if mid in metrics and (expected_value is None or
                        not isinstance(metrics[mid], (int, float)) or
                        not math.isclose(metrics[mid], expected_value, rel_tol=0, abs_tol=1e-8)):
                    problems.append(f"{name}: aggregate {mid} disagrees with rows")
        for entry in spec.get("slices", []):
            if entry.get("blocking") and not any(entry["name"] in value for value in tags.values()):
                problems.append(f"{name}: blocking slice {entry['name']} has no items")
    if len(identities) == 2 and identities[0] != identities[1]:
        problems.append("PR item/seed set differs from baseline")
    if len(slice_maps) == 2 and slice_maps[0] != slice_maps[1]:
        problems.append("PR slice membership differs from baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems.extend(_ratchet(spec, base_spec))
    return problems


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems = []
    for section, key in (("metrics", lambda m: m["id"]),
                         ("slices", lambda m: (m["name"], m["metric"]))):
        entries = {key(m): m for m in spec.get(section, [])}
        if len(entries) != len(spec.get(section, [])):
            problems.append(f"ratchet: duplicate {section}")
        for original in base_spec.get(section, []):
            ident = key(original)
            current = entries.get(ident)
            if current is None:
                problems.append(f"ratchet: removed {section} {ident}")
                continue
            if original.get("blocking") and not current.get("blocking"):
                problems.append(f"ratchet: disabled {ident}")
            old = original.get("threshold", {}) if section == "metrics" else original
            new = current.get("threshold", {}) if section == "metrics" else current
            for threshold in ("min", "max", "max_increase"):
                if threshold not in old:
                    continue
                value = new.get(threshold)
                if (not isinstance(value, (int, float)) or not math.isfinite(value)
                        or (threshold == "min" and value < old[threshold])
                        or (threshold != "min" and value > old[threshold])):
                    problems.append(f"ratchet: loosened {ident}/{threshold}")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"ratchet: removed paired comparison for {ident}")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        metric, name = entry["metric"], entry["name"]
        ident = f"slice:{name}/{metric}"
        left = per_item(pr, metric, slice_name=name)
        right = per_item(base, metric, slice_name=name)
        keys = sorted(left)
        failed = not keys or set(left) != set(right)
        value = sum(left.values()) / len(left) if left else None
        note = ""
        if value is not None:
            failed = failed or ("min" in entry and value < entry["min"])
            if entry.get("no_significant_drop") and keys and set(left) == set(right):
                delta, lo, hi = stats.paired_bootstrap(
                    [left[k] for k in keys], [right[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                note = f"delta {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed = failed or hi < 0
        if failed and entry.get("blocking"):
            blocked.append(ident)
        lines.append(f"  {ident} {value} {note} {'BLOCK' if failed else 'ok'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if not pr.get("manifest", {}).get("eval_set_sha") or pr.get("manifest", {}).get("eval_set_sha") != base.get("manifest", {}).get("eval_set_sha"):
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid) is not None:
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
