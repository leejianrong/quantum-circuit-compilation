# ADR-0002: Heavy DQI verification runs on a Kaggle notebook first, RunPod high-RAM pod as fallback

- Status: Accepted
- Date: 2026-11-10
- Deciders: Jian (F1, asked about RAM and Kaggle/Colab); recommendation by Claude

## Context

The baseline `dqi.kmb` is 886 MB. Local machine: WSL2, 7 GB total, about 1 GB free, 16 cores. The
verifier runs 400 batches x 256 shots (102,400 shots) over up to 4 forked workers
(`DEFAULT_MAX_WORKERS = 4`). The metric notes that verifier state grows only about 0.2 KB per
qubit/bit id (baseline ids stay below 50,000), so the state is small; the dominant memory term is
the parsed circuit itself. In-memory size per .kmb byte has **not been measured**, so the working
estimate is 2-10 GB for the baseline (parsed circuit plus simulation state; forked workers share it
copy-on-write). `kickmix.so` is compiled for Kaggle's image, and the real scoring runs there.

## Decision

1. Measure peak RSS of the baseline DQI verification once (`/usr/bin/time -v`) on Kaggle and record
   it in the ledger; this resolves the estimate.
2. Primary heavy executor: a Kaggle notebook (CPU notebooks have roughly 30 GB RAM and a long
   session limit; same image the scorer uses, so it eliminates "works locally, differs on Kaggle").
3. Fallback: RunPod high-RAM CPU pod via the `runpod-jobs` skill, if the Kaggle session limit, RAM
   or CPU count blocks the 10-salt margin runs.
4. Colab is not used: smaller RAM on the free tier, and a different OS image from the scorer.

## Alternatives considered

| Option | Why not |
|--------|---------|
| RunPod first | Costs money and is a different image from the scorer; only needed if Kaggle can't do it |
| Raise WSL memory | Host RAM unknown; worth trying for small runs only |
| Colab | Wrong image, smaller RAM |

## Consequences

DQI iteration goes through notebooks, so the harness needs a "run this remote" path (kaggle kernels
push/pull). As circuits shrink the need for remote runs fades. The RAM number is a placeholder until
V1 measures it.

## Measured (QCC-6, 2026-11-11, Kaggle script kernel `notebooks/dqi_verify/`)

| Circuit | Salts | Wall | Peak child RSS | Result |
|---|---|---|---|---|
| Baseline `dqi.kmb` (886 MB) | 2 | 472 s (about 4 min per salt) | 9.1 GB | PASS, cost 24,439,472,158,250 |
| Public best e9f54be3 (529 MB) | 10 | 1,303 s (about 2.2 min per salt) | 4.7 GB | PASS 10/10, cost 374.69e9 to 377.87e9 across salts |

Decision confirmed: Kaggle is the heavy executor (the baseline does not fit this 7 GB laptop; the
public best would only just). RunPod is not needed at this size. Reruns: edit the salt count in
`notebooks/dqi_verify/run.py` and `kaggle kernels push`.
