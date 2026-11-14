# Handoff: starting on a new machine

For a developer or agent taking over, for example on a machine with a GPU. Written 2026-11-14. Read this, then
[AGENTS.md](https://github.com/leejianrong/quantum-circuit-compilation/blob/main/AGENTS.md), then [COMPETITION.md](COMPETITION.md). Trust the code over any doc, and the ledger over both.

## Where we are

Ratios are `baseline_cost / cost` from the **official verifier** (worst salt). The leaderboard entry (25.218, submission
58244710) is a portfolio of other participants' public circuits that we verified ourselves; our own circuits are listed
beside the public ones they have to beat.

| Benchmark | Our own best (verified) | Public best we have measured | What is in `best/` |
|---|---|---|---|
| invsqrt | 12.34 (E023, 10 salts; own sqrt-division V2 7.37) | 25.9 (syed3000, 80,162.7) | `c6519219`, 21.95 |
| dqi | **65.77** (convert decoder `--gen fixed`, 890 qubits, 10 salts, 0 failures, Kaggle kernel `qcc-dqi-gen`) | 67.4 (syed3000, 889 qubits) | `e9f54be3`, about 65 |
| dfthcsos | 2.50 (E040, fully-own 11-bit ANF loader, 3 salts) | 11.31 (syed3000, 296.6M), 11.20 (`91d0ad25`) | `91d0ad25`, 11.20 |

Own DQI is within 3% of the best public circuit and is the closest thing to a promotable win; it has **not** been promoted
(`bench promote dqi <fixed.kmb> --dry-run` passes the gate; promotion needs the owner's say-so). invsqrt and dfthcsos are
far behind the public frontier.

What the last rounds established (all in `docs/experiments/`, newest first):

- dfthcsos: the gap to 11.3 is a different fit basin. Our `Lambda` is 490 to 560 for every fit against 283 for the public refit,
  and longer dense fits do not lower it (`dfthcsos-stage2.md`, "Lambda across our fits"). 8-bit rounding (QAT) lands at
  `error_2` 0.083 to 0.086 against a 0.02 gate, 10 bits at 0.027, whatever the continuous fit; 11 bits passes (E040).
  Structured starts (centered, sparse) end worse. An L1 term at the end of the fit trades `Lambda` for `error_2` 1:1, which is a poor trade.
- DQI: our extract stage is the public kernel verbatim and the extract plus synthesis round trip is within 0.6% of the public
  circuit; the mask gauge is worth at most 0.2% (`dqi-stage2.md`). More gain needs a different decoder design.
- invsqrt is parked unless there is a concrete new idea (`invsqrt-*.md`).

## Open questions for the owner

1. May syed3000's builders (Apache-2.0 source) be run in a sandbox to regenerate their circuits? The permission classifier blocks
   running third-party builders directly; this is the owner's decision (not taken).
2. GPU for dfthcsos fits: is a run with a `Lambda` penalty from the start worth the quota? See "GPU work" below.
3. Which licensed portfolio is submitted (`docs/PROVENANCE.md`, licence column; nothing is promoted or submitted without the owner).

## Standing instructions from the owner

(These also live in the previous machine's agent memory; they are repeated here so they travel.)

- Merge PRs yourself once CI is green (`gh pr merge --squash --delete-branch`); no attribution lines in commits or PRs.
- Be as aggressive and efficient as possible; do not frame work around the deadline. Reverse engineering other people's
  circuits is approved (syed3000's Apache-2.0 circuits for reference; the Apache-2.0 `andigu/uncompute` repo may be ported with
  notices). Our own code is written fresh and every idea is logged in `docs/PROVENANCE.md` (ADR-0009 and both 2026-11-13 amendments).
- Never promote into `best/` or submit without the owner's say-so. Promotion only through `bench promote` (dry-run it from the
  checkout where `best/` exists).
- Do not run third-party builders. No RunPod (balance low). The pod `fraktal-stage0` belongs to another project: never touch it.
- The Kaggle notebook `leejianrong/qcc-rebuild-and-verify-the-public-portfolio` stays private; the first public notebook
  is for circuits of ours that beat the public frontier.
- Use worktree-isolated sub-agents (at most 4, no nested agents), small PRs, `make check` before pushing.
- Resource limits of the old laptop (7 GB RAM, shared): official verifier runs under `flock /tmp/qcc-heavy.lock`; full-size DQI
  only on Kaggle. A bigger machine relaxes this, but keep one heavy verify at a time.

## First hour on a new machine

```bash
git clone https://github.com/leejianrong/quantum-circuit-compilation && cd quantum-circuit-compilation
make install && make hooks && make check           # no data needed
# Kaggle: put credentials in ~/.kaggle/credentials.json (or kaggle.json), accept the competition rules once in the browser
make fetch-data                                     # data/ (about 1 GB)
bash scripts/fetch_public.sh                        # public/ (about 2 GB) + public/MANIFEST.tsv
QCC_DATA=$PWD/data uv run bench verify dfthcsos data/sample_submission/dfthcsos --salts 1   # smoke test, appends a ledger row
```

Then pandan: install the CLI (see the `pandan` skill), `pandan login --token-stdin` with a PAT minted on the board's Tokens tab,
`pandan board use 46`. The agent config (`.mcp.json`, holds a token) is never committed: recreate it.

kickmix: use the pip wheel that `make install` gives you. `data/kickmix/kickmix.so` needs a newer libstdc++ than the old WSL
host had; on a modern machine it may work, but never put `data/kickmix` ahead of the wheel on `sys.path` unless you checked.

## Everything that is not in git, and where it came from

Git holds code, docs, ledgers (`ledger/*.jsonl`, append-only) and the vendored Apache-2.0 sources in `third_party/`. These are
**not** in git:

| Path | What | Origin and how to get it back |
|---|---|---|
| `data/` (1 GB) | competition data: verifiers, kickmix, sample submissions, FCIDUMP, baseline circuits | `make fetch-data` (Kaggle CLI, competition `google-verifiable-quantum-circuit-compilation`). Never redistribute (rules B.4.b). |
| `public/` (1.9 GB) | other participants' public circuits and `MANIFEST.tsv` (sha256) | `bash scripts/fetch_public.sh`; each file has a row in `docs/PROVENANCE.md`. Third-party, licences as stated there, never committed. |
| `best/` (0.5 GB) | the circuits `bench pack` submits: `invsqrt c6519219`, `dqi e9f54be3`, `dfthcsos 91d0ad25` | populated by `bench promote` from the fetched public circuits (`public/`), with the hashes in `docs/PROVENANCE.md`. Re-promote on the new machine from `public/` after re-verifying at several salts; third-party, licences unresolved, never committed. |
| `out/` | plots, `submission.zip`, scratch builds | `uv run bench plots`, `bench pack`; regenerable, safe to delete. |
| `.venv/`, caches | environment | `make install`. |
| `~/qcc-circuits/` (about 1 GB) | our built circuits and syed3000 references | see below. |
| `~/qcc-fits/` (2.2 GB) | dfthcsos fits and QAT results, DQI Kaggle outputs | see below. |
| `/tmp/...` | verified scratch builds (e.g. the 11-bit E040 submission) | volatile; the ledger rows name the path but the files are regenerable. |
| `.claude/` | agent worktrees and local settings | local only; delete worktrees when their branch is merged. |
| `~/.kaggle/`, `~/.config/pandan/`, `.mcp.json` | credentials | owner-held secrets. Never copy through a chat or commit; recreate on the new machine. |
| agent memory (`~/.claude/projects/.../memory/`) | standing preferences | summarized above under "Standing instructions". |

### `~/qcc-circuits/`

| Directory | What | Regenerate |
|---|---|---|
| `invsqrt/` (`e023.kmb`, `sd_v0..2.kmb`) | our invsqrt: E023 (12.34) and the sqrt-division versions | `uv run python -m invsqrt_gen.cli --a 7 --frac 28,19,9 --guard 2 --pm1 --rnd --polish --reachable --radius 2 out/e023` (`docs/experiments/invsqrt-uncompute.md`); verify with `flock /tmp/qcc-heavy.lock env QCC_DATA=$PWD/data uv run bench verify invsqrt out/e023.kmb --salts 5`. `LICENSE.syed3000` sits there because ideas were studied. |
| `own_dfthcsos_11bit_anf/` | E040 submission directory (2.50) | `docs/experiments/dfthcsos-stage2.md`, "First fully-own candidate": fit-c, QAT 11 bits `--half`, then `dfthcsos_post.py --half --loader anf`. |
| `own_dfthcsos_11bit_fite/` | the fit-e variant (predicted 2.43, not verified) | same with fit-e; negative result. |
| `dqi/` (`dqi-bm-1855q-*.kmb`, 479 MB) | our own Berlekamp-Massey decoder, 1,855 qubits, ratio 7.86 (verified, 10 salts; superseded by `fixed`) | deterministic build: `python -m dqi_gen.instances --gen bm --instance full --save <file>` (needs about 5 to 9 GB; use the Kaggle kernel `notebooks/dqi_gen`, see `dqi-bm.md`). |
| `dfthcsos_syed3000/`, `syed_ref/`, `syed_src/` | syed3000's public circuits, checksums and source (Apache-2.0, studied) | Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` (`public/`, `scripts/fetch_public.sh`); licences in `THIRD_PARTY_NOTICES.md`. Reference only. |

### `~/qcc-fits/`

| Path | What | Regenerate |
|---|---|---|
| `own/tsym/tsym.npy` (68 MB) | dfthcsos fit target: FCIDUMP integrals plus the fixed symmetry shift | `QCC_DATA=$PWD/data uv run python scripts/dfthcsos_fit.py <dir>`; needs `data/`. |
| `kaggle/leejianrong__qcc-dfthcsos-{fit,fit-b,fit-c,fit-e,cen,sparse1,sparse2}/` | continuous fits `v.npy`, `w.npy`, `log.jsonl` (8,176,56 unless noted); fit-e `exact_8x176x56` is the best (`error_2` 0.01159) | Kaggle free-CPU kernels `notebooks/dfthcsos_fit*` (each a chain of L-BFGS runs, 6 to 20 hours); `uv run bench kaggle fetch leejianrong/qcc-dfthcsos-<name> --out ~/qcc-fits/kaggle`. fit-c (continuous 0.01471) is the base of E040. |
| `kaggle/leejianrong__qcc-dqi-gen/` (2.1 GB) | DQI kernel output: `fixed.kmb` (the 65.77 circuit), `rs.kmb`, `thiele.kmb`, logs, ledger rows | `uv run bench kaggle fetch leejianrong/qcc-dqi-gen --out ~/qcc-fits/kaggle` (the kernel's output stays on Kaggle; rerun with `uv run bench kaggle run notebooks/dqi_gen`, which builds `--gen fixed --instance full` and verifies at 10 salts, about 20 minutes; the generators are `reference, divstep, lanczos, bm, rs, thiele, fixed`). The submit candidate is `fixed.kmb`, sha256 `37d8047d5f4b...`. |
| `own/qat{8,10,11}_half_fit{c,e}/` | half-circle QAT results (`v.npy`, `w.npy`, `words.npy`) | `scripts/dfthcsos_qat.py <fit> <out> --tsym <tsym> --brot <b> --half` (6 to 10 minutes each). Only 11 bits passes. |
| `repo/` copies in each kaggle dir | the cloned source the kernel ran | ignore. |

To rebuild everything the quick way: `make fetch-data`, `scripts/fetch_public.sh`, `scripts/dfthcsos_fit.py` for `tsym`,
`bench kaggle fetch` for the kernels above. The fits are the only expensive items (hours of CPU); fetching them from
Kaggle is free.

## GPU work (dfthcsos fit)

- `scripts/run_fit_gpu.py` is the torch float64 version of `scripts/run_fit.py` (same objective, same checkpoint layout, so either
  can resume the other). Install torch yourself (`uv pip install torch`; it is not a project dependency). The parity test
  `tests/unit/test_dfthcsos_fit_torch.py` pins it to the numpy objective.
- `notebooks/dfthcsos_fit_gpu_a` and `_b` are Kaggle GPU kernels for it (never pushed: weekly GPU quota was spent).
- What to try on a GPU, in order: (1) the same objective with a `Lambda` penalty from the first iteration, not an L1 term at the end
  (public refit: `Lambda` 283 at `error_2` 0.02); (2) many more iterations from a sparse or centered start, judged on `Lambda` and
  8-bit QAT error, not continuous `error_2`; (3) the rounding polish that syed3000's search describes (`dfthcsos-stage2.md`,
  "Words and accuracy").
- Gates for any new table (`dfthcsos-low-brot.md`): `error_1 <= 0.02`, `error_2 <= 0.02`, `E_gap > 3.914898`, `Lambda > 49`;
  score is `lambda_eff * T_total * Q_total`, `lambda_eff = sqrt(E_gap (2 Lambda - E_gap))` (`dfthcsos-cost-model.md`).

## Backlog, in order

1. DQI: ask the owner to promote `fixed.kmb` (the gate passes); then look for a different decoder design (the extract and mask
   gauge are exhausted).
2. dfthcsos: the `Lambda` basin (above), then 8/10-bit words, then the matroid pair planner (`src/dfthcsos_gen/matroid.py`; the cut
   search is open; about 8% of `T_total` at best).
3. invsqrt: parked.
4. Housekeeping: `make plots-readme` after each result; keep `docs/PROVENANCE.md` and `THIRD_PARTY_NOTICES.md` current.

## Pitfalls that cost time before

- The ledger is append-only and `toffolis` in it is a static count, not the official cost. Reduced-shot and `kickmix-engine` rows are screening only.
- `Circuit.to_file(path)` writes text unless `format='kmb'`; a text file named `.kmb` is rejected silently.
- Squash merges leave local branches that look unmerged (`git branch --no-merged`); check PR state with `gh pr list --state all`.
- `ledger/results.jsonl` conflicts after a pull: take upstream, then append your new row.
- `bench kaggle fetch` blocks while the kernel is running; run it in the background.
- Heavy verifies: one at a time, under `flock /tmp/qcc-heavy.lock`.
