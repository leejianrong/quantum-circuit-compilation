"""The Circuits tab (view model in `dashboard.circuits`)."""

import indah

from dashboard import circuits

COLUMNS = ["bench", "circuit", "file", "instructions", "ccx", "peak_width", "modules", "cost_tier", "in_best"]


def circuits_tab() -> indah.Component:
    rows = circuits.entries()
    if not rows:
        return indah.Empty(
            "No circuits indexed yet",
            "Index the circuits in best/ and write their explorer pages with:",
            children=[indah.Code("make circuits")],
        )
    table = indah.Table([{k: r[k] for k in COLUMNS} for r in rows], label="Indexed circuits")
    return indah.Column(
        [
            indah.Text(
                "Each circuit has a standalone page: an overview strip of inferred modules, and for "
                "any module its gate mix, wires and gates.",
                variant="caption",
            ),
            table,
            indah.Text(circuits.links_markdown(rows), markdown=True),
        ],
        gap="1rem",
    )
