"""Where does a DQI generator reach its qubit peak? Peak allocated qubits per stage, narrow instance (QCC-19).

    QCC_DATA=$PWD/data uv run python scripts/dqi_peak_stages.py v3s     # extractor: v2, v3 or v3s

Wraps the builder in a proxy that reads `num_allocated_qubits` after every allocation. A row is the stage tag
emitted last before the allocation, so "stage:synthesis_fwd" is the stage that follows it (outer forward).
"""

import collections
import sys
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen import fixed, host, instances


class Proxy:
    def __init__(self) -> None:
        self._b = km.CircuitBuilder()
        self.stage = "init"
        self.peak: dict[str, int] = collections.defaultdict(int)

    def info_tag(self, tag: str, *a: Any, **k: Any) -> Any:
        self.stage = tag
        return self._b.info_tag(tag, *a, **k)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._b, name)
        if not (name.startswith("alloc") or name.startswith("create_quantum")):
            return attr

        def wrap(*a: Any, **k: Any) -> Any:
            r = attr(*a, **k)
            self.peak[self.stage] = max(self.peak[self.stage], self._b.num_allocated_qubits)
            return r

        return wrap


def main() -> None:
    host.verifier()
    inst = instances.INSTANCES["narrow"]
    px = Proxy()
    fixed.km.CircuitBuilder = lambda: px  # type: ignore[assignment]
    c = fixed.build_circuit(inst.m, inst.n, inst.degree, stage_log="/dev/null", extractor=sys.argv[1])
    print("circuit qubits", c.num_qubits)
    for stage, q in sorted(px.peak.items(), key=lambda kv: -kv[1])[:8]:
        print(q, stage)


if __name__ == "__main__":
    main()
