import json
import pathlib
import subprocess

import pytest

from bench import remote


class FakeKaggle:
    """Stands in for the kaggle CLI: scripted statuses, and an output dir it fills on `kernels output`."""

    def __init__(self, statuses: list[str], ledger_lines: list[str] | None = None) -> None:
        self.statuses, self.ledger_lines, self.calls = list(statuses), ledger_lines or [], []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        out = ""
        if args[:2] == ["kernels", "status"]:
            out = f'x has status "KernelWorkerStatus.{self.statuses.pop(0)}"'
        elif args[:2] == ["kernels", "push"]:
            out = "Kernel version 1 successfully pushed."
        elif args[:2] == ["kernels", "output"]:
            d = pathlib.Path(args[args.index("-p") + 1]) / "ledger"
            d.mkdir(parents=True, exist_ok=True)
            (d / "results.jsonl").write_text("".join(ln + "\n" for ln in self.ledger_lines))
        return subprocess.CompletedProcess(args, 0, out, "")


ROW = json.dumps({"bench": "dqi", "cost": 1.0, "circuit_sha256": "a" * 64})


def test_wait_polls_until_terminal() -> None:
    fk, slept = FakeKaggle(["QUEUED", "RUNNING", "COMPLETE"]), []
    assert remote.wait("o/s", fk, poll=5, sleep=slept.append, log=lambda _: None) == "COMPLETE"
    assert slept == [5, 5]


def test_wait_times_out() -> None:
    fk = FakeKaggle(["RUNNING"] * 10)
    with pytest.raises(TimeoutError):
        remote.wait("o/s", fk, poll=5, timeout=10, sleep=lambda _: None, log=lambda _: None)


def test_error_status_is_terminal() -> None:
    assert remote.parse_status('has status "KernelWorkerStatus.ERROR"') == "ERROR"
    assert remote.wait("o/s", FakeKaggle(["ERROR"]), sleep=lambda _: None, log=lambda _: None) == "ERROR"


def test_merge_ledger_is_idempotent(tmp_path: pathlib.Path) -> None:
    src, dst = tmp_path / "r.jsonl", tmp_path / "l.jsonl"
    src.write_text(ROW + "\n")
    assert remote.merge_ledger(src, dst) == 1
    assert remote.merge_ledger(src, dst) == 0
    assert dst.read_text() == ROW + "\n"


def test_merge_ledger_rejects_non_json(tmp_path: pathlib.Path) -> None:
    src, dst = tmp_path / "r.jsonl", tmp_path / "l.jsonl"
    src.write_text("not json\n")
    with pytest.raises(ValueError):
        remote.merge_ledger(src, dst)
    assert not dst.exists()


def test_run_kernel_pushes_waits_fetches_and_merges(tmp_path: pathlib.Path) -> None:
    kdir = tmp_path / "k"
    kdir.mkdir()
    (kdir / "kernel-metadata.json").write_text(json.dumps({"id": "me/kern"}))
    led = tmp_path / "ledger.jsonl"
    fk = FakeKaggle(["RUNNING", "COMPLETE"], [ROW])
    code = remote.run_kernel(kdir, led, tmp_path / "out", fk, poll=0, timeout=10)
    assert code == 0
    assert [c[1] for c in fk.calls] == ["push", "status", "status", "output"]
    assert led.read_text() == ROW + "\n"
    assert (tmp_path / "out" / "me__kern" / "ledger" / "results.jsonl").exists()


def test_errored_kernel_returns_nonzero_but_still_fetches(tmp_path: pathlib.Path) -> None:
    led = tmp_path / "ledger.jsonl"
    code = remote.fetch_kernel("me/kern", led, tmp_path / "out", FakeKaggle(["ERROR"], [ROW]), 0, 1)
    assert code == 1 and led.exists()
