from invsqrt_gen.port.repeats import analyse

# q0 & q1 is computed twice into scratch wires; the second CCX repeats the first product.
TEXT = """X q21
X q21
CCX q0 q1 q22
CCX q0 q1 q23
"""


def test_repeated_product_is_found_but_not_holdable_at_peak_width() -> None:
    r = analyse(TEXT, samples=64, seed=0)
    pairs = r["pairs"]
    assert isinstance(pairs, list) and len(pairs) == 1
    # the gap includes the step where the second scratch wire goes live: that is the peak, so no spare wire
    assert pairs[0]["gap_peak"] == r["peak"]
    assert not pairs[0]["holdable"]


def test_distinct_products_are_not_repeats() -> None:
    r = analyse(TEXT.replace("CCX q0 q1 q23", "CCX q0 q2 q23"), samples=64, seed=0)
    assert r["pairs"] == []
