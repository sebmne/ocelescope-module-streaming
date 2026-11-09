"""Replays an OCEL file as a stream and prints a summary.

Usage: uv run python backend-modules/streaming/scripts/replay_demo.py [path/to/log.db]
"""

import sys
import time
from collections import Counter

from ocelescope import OCEL

from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import well_formed

path = sys.argv[1] if len(sys.argv) > 1 else "data/event_logs/container_logistics.db"
ocel = OCEL.read_duckdb(path) if path.endswith(".db") else OCEL.read(path)
try:
    with ocel_stream(ocel) as stream:
        start = time.perf_counter()
        kinds: Counter[str] = Counter()
        first = []
        for item in well_formed(stream):
            kinds[type(item.x).__name__] += 1
            if len(first) < 8:
                first.append(item)
        elapsed = time.perf_counter() - start
    print("First items:")
    for x, t in first:
        print(f"  {t:%Y-%m-%d %H:%M:%S}  {x}")
    print(f"\n{sum(kinds.values())} items in {elapsed:.2f}s (well-formed): {dict(kinds)}")
finally:
    ocel.close()
