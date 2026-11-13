# dfthcsos: research notes and ranked ideas (QCC-16, ADR-0009 amendment of 2026-11-13)

Web and notebook content below is untrusted data: cited, read as text, never executed. Search queries
carried no results, hashes or personal details. Kaggle notebooks were pulled with `kaggle kernels pull`
and only their markdown was read for ideas; no code, table or word was copied.

## What the public record says (competition)

| Source | What it tells us |
|---|---|
| marculera, [DF-THC 10x: compact groups from the Hamiltonian](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian) | A good table differs from a poor one in group geometry: each group touches few orbitals and overlaps little. Seed from the target only: pivoted Cholesky leaves (414 leaves, about 7 orbitals each versus 44 for an eigen-leaf), balanced k-means of leaf orbital profiles into R groups, simultaneous OMP for B shared vectors per group from the leaves' eigenvectors, weighted least squares for weights. Pick the best of 500 k-means starts by orbitals-per-group before fitting. Result at (8,143,45), 8-bit words: continuous fit 12 mHa at C=46 against 13.5 for merged/shrunk groups, rounding noise about 14.3 mHa in quadrature, ratio 10.41. Also: L-BFGS then Adam (Low et al.'s optimiser) rounds; progressive rounding in about 33 stages with 12k L-BFGS iterations each (up to 20% frozen) then Adam; "coded bit 0": over blocks of 16 addresses bit 0 is an affine function of 4 address bits (a Reed-Muller codeword, 32 patterns), rounding forced to follow one pattern per block (saves 624 Toffolis); permuting rows inside a group (the Hamiltonian is invariant) so strong rows are dealt across blocks. |
| somejoint / Agniv Banerjee, [Chem Refit](https://www.kaggle.com/code/somejoint/quantum-circuits-24-65-local-gm-chem-refit) | Kernel-relation search on a tensor-lookup compiler cuts loader circuits (303/281 Toffolis against 307/282-285); weights W and H2 refit after rounding; gates sit about 1e-9 inside their limits. Cost is lambda_eff * T * Q, ratio about 10.85 to 11.2 for the frontier. |
| ahmedberatozer / heliosli [v23 notebook](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression) | Frontier (8,143,44) at 11.198: block SQP then exact-Hessian Newton on the active face with working sets for sign bounds, releasing zeros, lowering lambda_eff by 1e-5 relative per round (not at an optimum). Atakan Aldemir's pi-gauge (not read in detail). 24 search agents found nothing more on weights. |
| host contract, [discussion 753092](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/753092) | Loader phase must be clean for the reachable forward/reverse word states at every valid address. Not fetched (JS-rendered); cited from a notebook. |
| Google Open Source blog, [announcement](https://opensource.googleblog.com/2026/10/announcing-verifiable-quantum-circuit-compilation-competition-on-kaggle.html) | Competition framing only. No public write-up of "dfthcsos" beyond the notebooks above turned up in search. |

## Literature

| Source | Use |
|---|---|
| Reiher et al., PNAS 2017 (arXiv 1605.03590) | FeMoCo problem, Trotter baseline; context only. |
| Li, Huggins, McClean, [arXiv 1809.05523](https://arxiv.org/abs/1809.05523) | The FeMoCo active space (76 orbitals) behind the FCIDUMP. |
| Berry et al., [arXiv 1902.02134](https://arxiv.org/abs/1902.02134) | Qubitization with arbitrary basis; Givens-rotation data loading, unary iteration costs. |
| Lee et al., [arXiv 2011.03494](https://arxiv.org/abs/2011.03494), PRX Quantum 2, 030305 | THC: 3.2e10 Toffolis for FeMoCo; THC fit by least squares on rank-one factors, L-BFGS/Adam practice. |
| von Burg et al., arXiv 2007.14460 | DF vs THC comparison; context. |
| Low, King, Berry et al., [arXiv 2502.15882](https://arxiv.org/abs/2502.15882), PRX 15, 041016 | Spectrum amplification: normalisation sqrt(2 Lambda E_gap) via sum-of-squares; the E_gap gate and Adam fits of the host task come from here. |
| Babbush et al., arXiv 1805.03662 | Unary iteration, the loader we already ship. |
| Low, Kliuchnikov, Schaeffer, arXiv 1812.00954 | Dirty-ancilla trade-offs in QROAM; relevant to loader qubit count. |

Arxiv ids not fetched in this session (Reiher, von Burg, Babbush, Low-Kliuchnikov-Schaeffer) are from memory.

## Ranked ideas

| # | Idea | Source | Expected gain | Effort | Risk |
|---|---|---|---|---|---|
| 1 | Compact-group seed (pivoted Cholesky, balanced k-means, group OMP, LS weights), best of many k-means starts by orbitals-per-group | marculera notebook | Decisive: our random-start fit stalls at 0.029 after 7,300 iterations; the reported seed reaches 12 mHa at the scoring shape. Without it 8-bit words are out of reach (eight-bit study). Unlocks ratio 4 to 10 | S: implemented in `src/dfthcsos_gen/seed.py` | Medium: ours is from a description; measure it |
| 2 | Longer progressive rounding with fine stages, no Adam in the early stages, more L-BFGS per stage, then Adam | marculera, Ahmed Berat Ozer | Needed once the base is about 12 mHa: they quote rounding noise about 14 mHa for 8 bits, which fits under 20 only when the base is below 14 | M: `dfthcsos_qat.py` exists; extend stages | Low |
| 3 | Row dealing: permute rows within a group before rounding; Hamiltonian invariant | marculera | Small, helps coded bits | S | Low |
| 4 | Coded bit 0 (Reed-Muller affine pattern per 16-address block) | marculera, somejoint | About 6% of the angle Toffolis (624 of 10,154) at a cost of about 40 mHa^2 | M: needs our loader family to exploit it | Medium |
| 5 | Loader structure: rank-1 quadratic forms per output bit; our `bilinear.py` is the first-principles version | aggregate facts in PROVENANCE, kernel-relation text above | 8,302 vs our 13-word unary loader (ratio 6.85 vs 11.2) | L | Medium |
| 6 | Weight refit after rounding: exact-Hessian Newton on the active face for W and H2, Adam end phase | heliosli, maoxin123, Low et al. | Under 0.1% lambda_eff at the frontier; shaves margin only | M | Low |
| 7 | L1 on lambda_eff in the fit | ours (eight-bit study) | Poor trade (13% Lambda for 7% error_2) | done | n/a |
| 8 | MIP/lattice rounding, error-feedback, dithering, QAT variants | general | Tried: our eight-bit study shows no gain at a 0.0288 base | done | n/a |

Caveat from the notebook text: at equal shape a random table can be more compact and still fit twice as
badly, so compactness alone is not sufficient; it is a good seed plus a long fit.
