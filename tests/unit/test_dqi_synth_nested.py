"""`set_synthesis_nested` switches the synthesis arithmetic and restores it."""

from dqi_gen import extract_v3


def test_toggle_and_restore() -> None:
    extract_v3.bind()
    import fused_crt_synthesis as fs  # type: ignore[import-not-found]

    extract_v3.set_synthesis_nested(False)
    original = fs.Arithmetic
    import gf24_nested_norm  # type: ignore[import-not-found]

    assert original is not gf24_nested_norm
    extract_v3.set_synthesis_nested(True)
    assert fs.Arithmetic is gf24_nested_norm
    extract_v3.set_synthesis_nested(False)
    assert fs.Arithmetic is original
