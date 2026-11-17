# Reading List

Papers for the project *Online Non-Preemptive Scheduling of Batch Jobs with Declared Time Limits*
(see [docs/problem_definition.pdf](../docs/problem_definition.pdf)).

Every entry has a link. DOI links lead to the publisher's page and may need the university library
login; arXiv, NeurIPS and author-page links are free.

Put the PDFs in this folder, using the file name in the last column of each table. PDFs in this folder
are ignored by git (`.gitignore`), because most of them are copyrighted; only this list is tracked.

**How far each entry was checked** (none was read in full):

- ✓ title, authors and main claim checked against the abstract or the paper's text
- ~ known only from secondary sources or search-result summaries; check before citing

Notation: $u_j$ declared limit, $p_j$ true running time, $u_j/\lambda \le p_j \le u_j$, $m$ machines.

---

## Suggested order

1. Hoogeveen & Vestjens 1996 (A1)
2. Schwiegelshohn 2022 (A2)
3. Azar, Leonardi & Touitou 2021 (B1): introduction and model
4. Gupta, Kumar, Panigrahi & Wang 2026 (B4)
5. Mu'alem & Feitelson 2001 and Tsafrir et al. 2007 (D1, D2): the sections on user estimates
6. The rest as needed

---

## A. The clairvoyant end ($\lambda = 1$): online $\sum C_j$ with known sizes

Must read. This is one end of our problem, and the delayed-start proofs are the technique to learn.

| # | Paper | Why it matters | Check | File name |
| --- | --- | --- | --- | --- |
| A1 | J. A. Hoogeveen, A. P. A. Vestjens. *Optimal on-line algorithms for single-machine scheduling.* IPCO 1996. [doi:10.1007/3-540-61310-2_30](https://doi.org/10.1007/3-540-61310-2_30) | Delayed SPT is 2-competitive on one machine and no deterministic algorithm does better. Source of our Delayed-SLF baseline. | ~ | `hoogeveen_vestjens_1996.pdf` |
| A2 | U. Schwiegelshohn. *Online Total Completion Time Scheduling on Parallel Identical Machines.* 2022. [arXiv:2207.08550](https://arxiv.org/abs/2207.08550) | Extends delayed SPT to $m$ machines: ratio at most 1.546 for even $m$ (previous best 1.791), tight for $m = 2$; improved lower bounds. The current state of the art for $\lambda = 1$, $m > 1$. | ✓ | `schwiegelshohn_2022.pdf` |
| A3 | X. Lu, R. A. Sitters, L. Stougie. *A class of on-line scheduling algorithms to minimize total completion time.* Oper. Res. Lett. 31(3), 2003. [doi:10.1016/S0167-6377(03)00016-6](https://doi.org/10.1016/S0167-6377(03)00016-6) | A family of 2-competitive delayed rules with a shorter proof. | ✓ | `lu_sitters_stougie_2003.pdf` |
| A4 | J. Tao, Z. Chao, Y. Xi. *A semi-online algorithm and its competitive analysis for a single machine scheduling problem with bounded processing times.* J. Ind. Manag. Optim. 6(2), 269-282, 2010. [doi:10.3934/jimo.2010.6.269](https://doi.org/10.3934/jimo.2010.6.269). Free conference version: [IMECS 2009 PDF](https://www.iaeng.org/publication/IMECS2009/IMECS2009_pp592-597.pdf) | One machine, sizes known, with $p_{\max}/p_{\min} \le \gamma$: ratio $1 + \frac{\gamma-1}{1+\sqrt{1+\gamma(\gamma-1)}} < 2$. The clairvoyant counterpart of our bounded-ratio setting. The ratio is from the IMECS version; the objective of the journal version was not checked. | ~ | `tao_chao_xi_2010.pdf` |

Optional, only for a randomized extension:

| # | Paper | Why it matters | Check | File name |
| --- | --- | --- | --- | --- |
| A5 | C. Chekuri, R. Motwani, B. Natarajan, C. Stein. *Approximation techniques for average completion time scheduling.* SIAM J. Comput. 31(1), 2001. [doi:10.1137/S0097539797327180](https://doi.org/10.1137/S0097539797327180) | Randomized $e/(e-1)$ on one machine. | ✓ | `chekuri_et_al_2001.pdf` |
| A6 | L. Stougie, A. P. A. Vestjens. *Randomized algorithms for on-line scheduling problems: how low can't you go?* Oper. Res. Lett. 30(2), 89-96, 2002. [DBLP record](https://dblp.org/rec/journals/orl/StougieV02) (DOI not found) | Matching randomized lower bound. | ✓ | `stougie_vestjens_2002.pdf` |

---

## B. Size estimates with bounded multiplicative error (closest line of work)

The scheduler has an estimate of each job's size that is off by a factor of at most $\mu$ (the
"distortion"). This is the same idea as our $\lambda$. **All of these allow preemption and minimize
flow time.** We found no paper on the non-preemptive $\sum C_j$ version; check the related-work sections
of these papers again before claiming that.

| # | Paper | Why it matters | Check | File name |
| --- | --- | --- | --- | --- |
| B1 | Y. Azar, S. Leonardi, N. Touitou. *Flow Time Scheduling with Uncertain Processing Time.* STOC 2021. [arXiv:2103.05604](https://arxiv.org/abs/2103.05604) | Introduces the model and the distortion $\mu$. | ✓ | `azar_leonardi_touitou_2021.pdf` |
| B2 | Y. Azar, S. Leonardi, N. Touitou. *Distortion-Oblivious Algorithms for Minimizing Flow Time.* SODA 2022. [arXiv:2109.08424](https://arxiv.org/abs/2109.08424) | The algorithm does not need to know $\mu$. Compare with our assumption that $\lambda$ is known. | ~ | `azar_leonardi_touitou_2022.pdf` |
| B3 | Z. Scully, I. Grosof, M. Mitzenmacher. *Uniform Bounds for Scheduling with Job Size Estimates.* ITCS 2022. [arXiv:2110.00633](https://arxiv.org/abs/2110.00633) | Estimates within $[\beta s, \alpha s]$ of the true size $s$; queueing (M/G/1) view; SRPT on estimates can be arbitrarily bad. | ✓ | `scully_grosof_mitzenmacher_2022.pdf` |
| B4 | A. Gupta, A. Kumar, D. Panigrahi, Z. Wang. SODA 2026. [PDF](https://users.cs.duke.edu/~debmalya/papers/soda26-flowtime.pdf) | $O(\mu)$-competitive algorithm for total flow time on one machine, distortion-oblivious. Title to be taken from the PDF. | ~ | `gupta_et_al_soda2026.pdf` |
| B5 | A. Gupta, H. Kaplan, A. Lindermayr, J. Schlöter, S. Yingchareonthawornchai. *Better Late Than Never: Online Flow Time Scheduling with Online Estimates.* 2026. [arXiv:2609.07402](https://arxiv.org/abs/2609.07402) | Estimates arrive while the job runs; $O(\mu/\varepsilon)$-competitive and optimal. | ✓ | `gupta_et_al_2026_online_estimates.pdf` |
| B6 | Z. Chen, Ye, Zhou. 2025. [arXiv:2508.14544](https://arxiv.org/abs/2508.14544) | Sizes known to lie in an interval $[l, u]$ (LLM inference); all jobs released at time 0, with batching and cancellation. Closest formal cousin from the industry side. Title and first names to be confirmed. | ~ | `chen_ye_zhou_2025.pdf` |

---

## C. Unknown sizes (the $\lambda \to \infty$ end) and predictions

| # | Paper | Why it matters | Check | File name |
| --- | --- | --- | --- | --- |
| C1 | R. Motwani, S. Phillips, E. Torng. *Non-clairvoyant scheduling.* Theor. Comput. Sci. 130(1), 1994. [doi:10.1016/0304-3975(94)90151-1](https://doi.org/10.1016/0304-3975(94)90151-1) | The founding paper of non-clairvoyant scheduling. | ~ | `motwani_phillips_torng_1994.pdf` |
| C2 | S. Jäger, G. Sagnol, D. Schmidt genannt Waldschmidt, P. Warode. *Competitive Kill-and-Restart and Preemptive Strategies for Non-Clairvoyant Scheduling.* IPCO 2023; Math. Programming 2024. [arXiv:2211.02044](https://arxiv.org/abs/2211.02044) | With unknown sizes, non-preemptive algorithms are not constant-competitive (claim seen only in a summary); kill-and-restart as the alternative. Motivates a bounded $\lambda$. | ✓ title/abstract, ~ the claim | `jaeger_et_al_2023.pdf` |
| C3 | M. Purohit, Z. Svitkina, R. Kumar. *Improving Online Algorithms via ML Predictions.* NeurIPS 2018. [proceedings](https://proceedings.neurips.cc/paper/2018/hash/73a427badebe0e32caa2e1fc7530b7f3-Abstract.html) | Start of scheduling with predictions. Our $u_j$ is a prediction with bounded one-sided error. | ~ | `purohit_svitkina_kumar_2018.pdf` |
| C4 | A. Lindermayr, N. Megow. *Permutation Predictions for Non-Clairvoyant Scheduling.* SPAA 2022. [arXiv:2202.10199](https://arxiv.org/abs/2202.10199) | Predicts the order of jobs instead of sizes; preemptive. | ✓ | `lindermayr_megow_2022.pdf` |
| C5 | Z. Benomar, R. Cosson, A. Lindermayr, J. Schlöter. *Non-Clairvoyant Scheduling with Progress Bars.* NeurIPS 2025. [arXiv:2509.19662](https://arxiv.org/abs/2509.19662) | Recent work on predictions; also improves bounds for size predictions. Preemptive. | ✓ | `benomar_et_al_2025.pdf` |
| C6 | Geng, Sun, Yang, Zhang. 2025. [arXiv:2511.03485](https://arxiv.org/abs/2511.03485) | Non-preemptive online total flow time, bounds in $n$ and $m$. Title and first names to be confirmed. | ~ | `geng_et_al_2025.pdf` |
| C7 | H. Kellerer, T. Tautenhahn, G. J. Woeginger. *Approximability and nonapproximability results for minimizing total flow time on a single machine.* SIAM J. Comput. 28(4), 1999. [doi:10.1137/S0097539796305778](https://doi.org/10.1137/S0097539796305778) | Offline non-preemptive total flow time is hard to approximate. A reason to state theory for $\sum C_j$. | ~ | `kellerer_et_al_1999.pdf` |

---

## D. Industry background: declared time limits in HPC

Read the sections on user estimates; the backfilling details are not needed.

| # | Paper | Why it matters | Check | File name |
| --- | --- | --- | --- | --- |
| D1 | A. W. Mu'alem, D. G. Feitelson. *Utilization, predictability, workloads, and user runtime estimates in scheduling the IBM SP2 with backfilling.* IEEE TPDS 12(6), 2001. [author PDF](https://www.cse.huji.ac.il/~feit/papers/SP2backfil01TPDS.pdf) | User estimates are very inaccurate; actual run times are spread widely below the estimate. | ~ | `mualem_feitelson_2001.pdf` |
| D2 | D. Tsafrir, Y. Etsion, D. G. Feitelson. *Backfilling using system-generated predictions rather than user runtime estimates.* IEEE TPDS 18(6), 2007. [author PDF](https://www.cse.huji.ac.il/~feit/papers/Pred07TPDS.pdf) | Users pick from a few round values: about 90% of jobs use the same 20 values. | ~ | `tsafrir_etsion_feitelson_2007.pdf` |
| D3 | JSSPP 2025 paper from Boston University and Sandia. [PDF](https://www.bu.edu/peaclab/files/2025/09/JSSPP_2025_paper_19-1.pdf) | Recent evidence, from the logs of five HPC systems, that requested wall times are still inaccurate. Title and authors to be taken from the PDF. | ~ | `jsspp_2025_paper19.pdf` |

Documentation (web pages, nothing to download):

- Slurm: [sbatch](https://slurm.schedmd.com/sbatch.html) (`--time`), [slurm.conf](https://slurm.schedmd.com/slurm.conf.html) (`MaxTime`), [preemption](https://slurm.schedmd.com/preempt.html)
- Parallel Workloads Archive: [traces](https://www.cs.huji.ac.il/labs/parallel/workload/), [SWF format](https://www.cs.huji.ac.il/labs/parallel/workload/swf.html)

---

## Open literature questions

- Is there prior work on exactly our problem (online arrivals, non-preemptive, $p_j \in [u_j/\lambda, u_j]$,
  objective $\sum C_j$)? Search terms to try: "semi-clairvoyant scheduling", "scheduling with uncertain
  processing times", "interval processing times online", "robust scheduling distortion non-preemptive".
- Does any paper in group B treat a non-preemptive variant in its related work or open problems?
