"""Generates reference trees of the Rust DF2 cut miner for tests/test_ocpt.py.

The harness in `scripts/cut_harness` wraps `find_cuts_start` from a checkout of
BPM-Research-Group/scope. Usage:

    uv run python scripts/cut_miner_reference.py /path/to/scope

It copies the miner sources into the harness, builds it with cargo, runs it on random DF2 graphs
and on the DF2 graphs of the bundled logs, and writes tests/reference/cut_miner_cases.json.
"""

import json
import random
import re
import subprocess
import sys
from pathlib import Path

from ocelescope import OCEL

from ocelescope_module_streaming.algorithms import offline_df2

HERE = Path(__file__).resolve().parent
HARNESS = HERE / "cut_harness"
OUTPUT = HERE.parent / "tests" / "reference" / "cut_miner_cases.json"
LOGS = HERE.parents[2] / "data" / "event_logs"


def prepare_harness(scope: Path) -> Path:
    miner = scope / "backend" / "src" / "core" / "df2_miner"
    opti = (miner / "start_cuts_opti.rs").read_text()
    opti = re.sub(
        r"^use crate::core::df2_miner::start_cuts::\{[^}]*\};\n",
        "use crate::start_cuts::{is_exclusive_choice_cut_possible, is_sequence_cut_possible};\n",
        opti,
        flags=re.M,
    )
    opti = re.sub(
        r"^use crate::\{\n.*?\};\n",
        "use crate::start_cuts::is_reachable;\nuse crate::{ProcessForest, TreeNode};\n",
        opti,
        flags=re.M | re.S,
    )
    opti = opti.replace("use log::info;\n", "")
    header = "#![allow(dead_code, unused_imports)]\nmacro_rules! info { ($($t:tt)*) => {} }\n"
    (HARNESS / "src" / "start_cuts_opti.rs").write_text(header + opti)
    cuts = (miner / "start_cuts.rs").read_text()
    functions = [
        re.search(r"pub fn " + name + r"\(.*?\n}\n", cuts, flags=re.S).group(0)  # type: ignore[union-attr]
        for name in ("is_reachable", "is_sequence_cut_possible", "is_exclusive_choice_cut_possible")
    ]
    imports = "use std::collections::{HashMap, HashSet};\n\n"
    (HARNESS / "src" / "start_cuts.rs").write_text(imports + "\n".join(functions))
    subprocess.run(["cargo", "build", "--release", "-q"], cwd=HARNESS, check=True)
    return HARNESS / "target" / "release" / "cutharness"


def random_case(rng: random.Random) -> dict[str, list]:
    activities = [chr(ord("a") + i) for i in range(rng.randint(2, 7))]
    density = rng.choice([0.15, 0.3, 0.5])
    edges = [[a, b] for a in activities for b in activities if rng.random() < density]
    return {
        "activities": activities,
        "edges": edges,
        "starts": rng.sample(activities, rng.randint(1, len(activities))),
        "ends": rng.sample(activities, rng.randint(1, len(activities))),
    }


def tree_case(rng: random.Random) -> dict[str, list]:
    """The directly-follows graph of a random process tree, so that all cut types occur."""
    names = iter(chr(ord("a") + i) for i in range(26))

    def build(depth: int) -> tuple[set[str], set[tuple[str, str]], set[str], set[str]]:
        if depth == 0 or rng.random() < 0.3:
            a = next(names)
            return {a}, set(), {a}, {a}
        operator = rng.choice(["seq", "xor", "par", "loop"])
        (a1, d1, s1, e1), (a2, d2, s2, e2) = build(depth - 1), build(depth - 1)
        acts, edges = a1 | a2, d1 | d2
        if operator == "seq":
            return acts, edges | {(x, y) for x in e1 for y in s2}, s1, e2
        if operator == "xor":
            return acts, edges, s1 | s2, e1 | e2
        if operator == "par":
            both = {(x, y) for x in a1 for y in a2} | {(y, x) for x in a1 for y in a2}
            return acts, edges | both, s1 | s2, e1 | e2
        return acts, edges | {(x, y) for x in e1 for y in s2} | {(x, y) for x in e2 for y in s1}, s1, e1

    activities, edges, starts, ends = build(rng.randint(1, 4))
    return {
        "activities": sorted(activities),
        "edges": sorted([a, b] for a, b in edges),
        "starts": sorted(starts),
        "ends": sorted(ends),
    }


def log_cases() -> list[dict[str, list]]:
    cases = []
    for path in sorted(LOGS.glob("*.db")):
        df2 = offline_df2(OCEL.read_duckdb(str(path)))
        cases.append(
            {
                "name": path.stem,
                "activities": df2.activities,
                "edges": [[e.source, e.target] for e in df2.edges],
                "starts": df2.start_activities,
                "ends": df2.end_activities,
            }
        )
    return cases


def main() -> None:
    binary = prepare_harness(Path(sys.argv[1]))
    rng = random.Random(7)
    cases = [random_case(rng) for _ in range(400)] + [tree_case(rng) for _ in range(400)] + log_cases()
    lines = []
    for case in cases:
        lines += [f"A\t{a}" for a in case["activities"]]
        lines += [f"S\t{a}" for a in case["starts"]]
        lines += [f"E\t{a}" for a in case["ends"]]
        lines += [f"D\t{a}\t{b}" for a, b in case["edges"]]
        lines.append("---")
    result = subprocess.run([binary], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    for case, expected in zip(cases, result.stdout.splitlines(), strict=True):
        case["rust"] = expected
    OUTPUT.write_text(json.dumps(cases, indent=None, separators=(",", ":")) + "\n")
    print(f"Wrote {len(cases)} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
