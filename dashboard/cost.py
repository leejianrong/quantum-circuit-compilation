"""Pure view model of the Cost explorer tab: no indah import, so it is tested without the extra.

The score is `lambda_eff x T_total x Q_total` from `dfthcsos_model`. What the model cannot know is
the accuracy of a table we have not fitted, so each table below carries the (error_1, error_2)
we measured at the word widths we ran and the gate status is one of:

- measured: the table, shape and width were run through the verifier's metrics;
- estimated: our own fit family at a width we did not run (log-linear in the width, error_1 halves per bit);
- not measured: a shape or loader we never fitted, so no claim about the gates.

Numbers come from `docs/experiments/dfthcsos-structured.md` and `tests/unit/test_dfthcsos_model.py`.
"""

import math
from dataclasses import dataclass

from dfthcsos_model import Angles, Breakdown, passes_gates, plain_qrom_angles, score
from dfthcsos_model.model import QUBIT_CAP, addresses
from dfthcsos_model.prepare import clog2, prepare_costs

BASELINE_COST = 3_355_599_588.3155365
PUBLIC_COST = 299_614_422.43592083  # public refit 91d0ad25, unverified by us except at 3 salts, see ledger
BROTS = tuple(range(4, 17))

# The public structured loader is measured at one setting; it does not scale with J.
PUBLIC_LOADER = Angles(toffoli=8302, qubits=128, J=5, brot=8)


@dataclass(frozen=True)
class Table:
    key: str
    name: str
    shape: tuple[int, int, int]
    lam: dict[int, float]  # Lambda per width (the nearest measured width is used elsewhere)
    e_gap: dict[int, float]
    errors: dict[
        int, tuple[float, float] | None
    ]  # width -> (error_1, error_2) measured; None = verified pass
    fails_below: int | None = None  # estimated own-fit family: widths under this fail error_2
    estimable: bool = False


TABLES: dict[str, Table] = {
    "baseline": Table(
        "baseline",
        "Host baseline table",
        (65, 60, 60),
        {12: 308.4559397330944},
        {12: 3.965477244291833},
        {12: None},
    ),
    "public": Table(
        "public",
        "Public refit table",
        (8, 143, 44),
        {8: 282.77473254974973},
        {8: 3.914898000250105},
        {8: None},
    ),
    "own": Table(
        "own",
        "Our own table (QCC-16)",
        (8, 176, 56),
        {10: 481.8, 11: 481.8, 12: 480.4},
        {10: 4.0898, 11: 4.0898, 12: 4.0906},
        {10: (0.0140, 0.0260), 11: (0.0070, 0.0179), 12: (0.0036, 0.0165)},
        fails_below=11,
        estimable=True,
    ),
}

# Verified points of the fully-own and public circuits, for the chart markers: (brot, cost, label).
VERIFIED = (
    (12, 1_850_153_217.1335442, "own 1.81x"),
    (11, 1_697_674_804.54712, "own 1.98x"),
    (8, 489_890_973.17878884, "public words, our loader 6.85x"),
    (8, PUBLIC_COST, "public 11.20x"),
)


@dataclass(frozen=True)
class Setting:
    R: int = 8
    B: int = 176
    C: int = 56
    brot: int = 11
    J: int = 9
    loader: str = "own"  # "own" (unary iteration, A - 2 Toffolis per circuit) or "public" (fixed counts)
    table: str = "own"


PRESETS: dict[str, Setting] = {
    "Host baseline": Setting(65, 60, 60, brot=12, J=8, loader="own", table="baseline"),
    "Public refit": Setting(8, 143, 44, brot=8, J=5, loader="public", table="public"),
    "Public table, our loader": Setting(8, 143, 44, brot=8, J=13, loader="own", table="public"),
    "Our 11-bit table": Setting(8, 176, 56, brot=11, J=9, loader="own", table="own"),
    "Our 12-bit table": Setting(8, 176, 56, brot=12, J=8, loader="own", table="own"),
}


def max_J(R: int, B: int, brot: int) -> int:
    """Largest J whose unary loader fits the 128-qubit cap (the same rule as `dfthcsos_gen.loader`)."""
    n = clog2(addresses(R, B))
    return max(0, (QUBIT_CAP - n - (n - 1)) // brot)


def angles_for(s: Setting, J: int | None = None) -> Angles:
    if s.loader == "public":
        return PUBLIC_LOADER
    j = s.J if J is None else J
    toff, scratch = plain_qrom_angles(s.R, s.B, j)
    return Angles(toffoli=toff, qubits=clog2(addresses(s.R, s.B)) + j * s.brot + scratch, J=j, brot=s.brot)


def _nearest(d: dict[int, float], brot: int) -> float:
    return d[min(d, key=lambda k: abs(k - brot))]


def estimate_errors(t: Table, brot: int) -> tuple[float, float]:
    """(error_1, error_2) of our own fit family at a width, interpolated in log error_2 between the
    measured widths and extended with the nearest slope; error_1 halves per bit."""
    pts = sorted((b, e[1]) for b, e in t.errors.items() if e)
    e1 = 0.0070 * 2.0 ** (11 - brot)
    if brot <= pts[0][0]:
        (b0, y0), (b1, y1) = pts[0], pts[1]
    elif brot >= pts[-1][0]:
        (b0, y0), (b1, y1) = pts[-2], pts[-1]
    else:
        b0, y0 = max(p for p in pts if p[0] <= brot)
        b1, y1 = min(p for p in pts if p[0] >= brot)
        if b0 == b1:
            return e1, y0
    slope = (math.log(y1) - math.log(y0)) / (b1 - b0)
    return e1, max(0.0138, math.exp(math.log(y0) + slope * (brot - b0)))  # continuous fit floor


@dataclass(frozen=True)
class Gate:
    status: str  # "pass", "fail" or "not measured"
    basis: str  # "measured", "estimated" or ""
    detail: str


def gate(s: Setting, lam: float, e_gap: float) -> Gate:
    t = TABLES[s.table]
    if (s.R, s.B, s.C) != t.shape:
        return Gate("not measured", "", f"{t.name} is fitted for shape {t.shape}; this shape needs a refit.")
    if s.loader != "own" and s.table != "public":
        return Gate("not measured", "", "The public loader is only measured with the public table.")
    if s.brot in t.errors:
        e = t.errors[s.brot]
        if e is None:
            return Gate("pass", "measured", "Verified by the official verifier.")
        ok = passes_gates(e[0], e[1], lam, e_gap)
        return Gate(
            "pass" if ok else "fail", "measured", f"error_1 {e[0]:.4f}, error_2 {e[1]:.4f} (limit 0.02)."
        )
    if t.estimable:
        e1, e2 = estimate_errors(t, s.brot)
        ok = passes_gates(e1, e2, lam, e_gap)
        return Gate(
            "pass" if ok else "fail",
            "estimated",
            f"error_1 about {e1:.4f}, error_2 about {e2:.4f} (limit 0.02); this width was not run.",
        )
    return Gate("not measured", "", f"{t.name} was only run at {sorted(t.errors)} bits.")


@dataclass(frozen=True)
class Result:
    setting: Setting
    breakdown: Breakdown
    angles: Angles
    gate: Gate
    cap_ok: bool  # the loader circuit fits 128 qubits

    @property
    def ratio(self) -> float:
        return BASELINE_COST / self.breakdown.score

    @property
    def vs_public(self) -> float:
        return self.breakdown.score / PUBLIC_COST


def evaluate(s: Setting, J: int | None = None) -> Result:
    t = TABLES[s.table]
    lam = _nearest(t.lam, s.brot)
    e_gap = _nearest(t.e_gap, s.brot)
    a = angles_for(s, J)
    b = score((s.R, s.B, s.C), a, lam, e_gap)
    return Result(s, b, a, gate(s, lam, e_gap), a.qubits <= QUBIT_CAP)


def chart_rows(s: Setting) -> list[list[float | None]]:
    """Rows `[brot, your J, largest J, your setting]` for the Chart (the last column is one dot).

    Your J is clamped to what fits the 128-qubit cap at each width; the public loader has no J.
    """
    rows: list[list[float | None]] = []
    for b in BROTS:
        at = Setting(s.R, s.B, s.C, b, s.J, s.loader, s.table)
        top = max(1, max_J(s.R, s.B, b))
        yours = evaluate(at, min(s.J, top)).breakdown.score
        best = evaluate(at, top).breakdown.score
        rows.append([b, yours, best, yours if b == s.brot else None])
    return rows


def cliffs(s: Setting) -> list[tuple[int, int]]:
    """Width pairs (lower, higher) where the inner QROAM workspace, and with it Q_total, steps up.

    The block exponent follows `75 * brot`, so going up in width crosses these edges; going down
    across the first one is the cheap direction, which is why a narrower table is worth fitting.
    """
    temp = {b: prepare_costs(s.R, s.B, s.C, b).inner_temp for b in BROTS}
    return [(b, b + 1) for b in BROTS[:-1] if temp[b + 1] > temp[b]]
