"""Build the ported upstream decoder (`dqi_gen/rs`) as a kickmix circuit for the benchmark instance.

The circuit is the discovered `dqi-reed-solomon` circuit of Gu, Kemeny, Yelin and Lukin (Apache-2.0, see
`THIRD_PARTY_NOTICES.md`) with the runtime-mask sweep; `uc2km` converts its op stream. Only the benchmark
shape `(n, degree) = (70, 12)` exists; `m` may be below 4095 for the verifier's small instances.
"""

from __future__ import annotations

from typing import Any

from dqi_gen import uc2km


def build_circuit(m: int, n: int, degree: int) -> Any:
    if (n, degree) != (70, 12):
        raise ValueError("the ported decoder is built for n = 70 syndromes over GF(2^12)")
    from dqi_gen import rs  # noqa: F401  (puts the vendored `uncompute` on sys.path)
    from dqi_gen.rs import circuit

    builder, _ = circuit.build(m)  # type: ignore[no-untyped-call]
    return uc2km.convert(builder, n_syn=n, deg=degree, n_err=m)
