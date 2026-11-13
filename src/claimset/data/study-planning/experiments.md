# Experiments and inference

Version 0.2 (draft, to be reviewed by someone who works in the field) · 2026-11-13

For studies that compare conditions, methods or groups, or estimate an effect: designed experiments, simulation
studies, observational comparisons and causal questions.

## Principle

A conclusion rests on what is estimated and how the comparison was decided. Say first what quantity the claim is
about (the estimand: which effect, on whom, compared with what), then choose the design and the analysis that estimate
it, and fix both before the data are seen ([Lundberg, Johnson and Stewart 2021](https://doi.org/10.1177/00031224211004187); [Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114)). The analysis answers the question the design was built
for, not the one that turned out convenient.

## estimand

- **When:** any comparison or effect.
- **Default:** state the estimand before the design: the population or cases, the conditions compared, the outcome,
  how events after assignment that change or end the outcome are handled (stopping or switching a treatment, a unit
  that drops out of the process studied), and the summary measure (a difference in means, a ratio, a share). This
  is the estimands framework of the ICH E9(R1) addendum for clinical trials ([Kahan et al. 2024](https://doi.org/10.1136/bmj-2023-076316)); outside trials, the same
  questions define the target quantity ([Lundberg, Johnson and Stewart 2021](https://doi.org/10.1177/00031224211004187)). Missing data are a matter of how the estimand is estimated, not of
  what it is.
- **Why:** a precise estimand connects the statistical result to the claim it supports; without it, the same data
  support several different claims, and the analysis can be chosen after the fact ([Lundberg, Johnson and Stewart 2021](https://doi.org/10.1177/00031224211004187); [Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114)).
- **References:** [Lundberg, Johnson and Stewart 2021](https://doi.org/10.1177/00031224211004187); [Kahan et al. 2024](https://doi.org/10.1136/bmj-2023-076316); [Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114).

## effect-sizes

- **When:** reporting any comparison.
- **Default:** report the size of the effect with its interval, not only whether a test rejected ([Cumming 2014](https://doi.org/10.1177/0956797613504966)).
- **Why:** a p-value does not measure the size of an effect or the importance of a result ([Wasserstein and Lazar 2016](https://doi.org/10.1080/00031305.2016.1154108)); an estimate with
  its interval shows how large the effect may be, against which its importance can be judged ([Cumming 2014](https://doi.org/10.1177/0956797613504966)).
- **Avoid:** "significant" or "not significant" as the finding ([Wasserstein, Schirm and Lazar 2019](https://doi.org/10.1080/00031305.2019.1583913)).
- **References:** [Wasserstein and Lazar 2016](https://doi.org/10.1080/00031305.2016.1154108); [Wasserstein, Schirm and Lazar 2019](https://doi.org/10.1080/00031305.2019.1583913); [Cumming 2014](https://doi.org/10.1177/0956797613504966).

## no-difference

- **When:** the claim is that there is no difference, or no meaningful one.
- **Default:** an equivalence test against bounds fixed in advance: the smallest difference that would matter
  ([Lakens 2017](https://doi.org/10.1177/1948550617697177)).
- **Why:** failing to reject a null hypothesis is not evidence of no difference ([Altman and Bland 1995](https://doi.org/10.1136/bmj.311.7003.485); [Lakens 2017](https://doi.org/10.1177/1948550617697177)).
- **References:** [Lakens 2017](https://doi.org/10.1177/1948550617697177); [Altman and Bland 1995](https://doi.org/10.1136/bmj.311.7003.485).

## multiple-tests

- **When:** several tests decide the claims of one study.
- **Default:** fix the correction in advance. Use Holm's procedure to control the family-wise error rate when each
  claim must stand on its own ([Holm 1979](https://www.jstor.org/stable/4615733)); it holds whatever the dependence between the tests. Use Benjamini–Hochberg to
  control the false discovery rate when many tests screen for effects ([Benjamini and Hochberg 1995](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)); it is proved for independent or
  positively dependent tests ([Benjamini and Yekutieli 2001](https://doi.org/10.1214/aos/1013699998)), and under arbitrary dependence the Benjamini–Yekutieli correction is needed
  ([Benjamini and Yekutieli 2001](https://doi.org/10.1214/aos/1013699998)).
- **Why:** without a correction, the chance of a false claim grows with the number of tests; a correction chosen
  after the results are seen can be chosen to fit them ([Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114)).
- **References:** [Holm 1979](https://www.jstor.org/stable/4615733); [Benjamini and Hochberg 1995](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x); [Benjamini and Yekutieli 2001](https://doi.org/10.1214/aos/1013699998).

## simulation-studies

- **When:** methods are evaluated on simulated data.
- **Default:** plan and report by aims, data-generating mechanisms, estimands, methods and performance measures
  (ADEMP); choose the number of repetitions for the Monte Carlo standard error you can accept, and report that error
  with each estimated performance measure ([Morris, White and Crowther 2019](https://doi.org/10.1002/sim.8086)).
- **References:** [Morris, White and Crowther 2019](https://doi.org/10.1002/sim.8086).

## preregistration

- **When:** any test meant to be confirmatory.
- **Default:** fix the research question, the hypotheses, the design and the analysis plan before the data are seen,
  in a record with a trustworthy time (in a claimset lab, the plan) ([Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114)).
- **Why:** a test is a prediction only when it was stated before the outcomes were seen; the same analysis chosen
  afterwards is a postdiction ([Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114)).
- **References:** [Nosek et al. 2018](https://doi.org/10.1073/pnas.1708274114).

## reporting

- **Default:** follow the reporting guideline for the design: CONSORT 2025 for randomised trials ([Hopewell et al. 2025](https://doi.org/10.1136/bmj-2024-081123)), STROBE for
  observational studies in epidemiology (cohort, case-control and cross-sectional) ([von Elm et al. 2007](https://doi.org/10.1016/S0140-6736%2807%2961602-X)), and others at the EQUATOR
  Network (<https://www.equator-network.org>). Simulation studies report by ADEMP ([Morris, White and Crowther 2019](https://doi.org/10.1002/sim.8086)).
- **References:** [Hopewell et al. 2025](https://doi.org/10.1136/bmj-2024-081123); [von Elm et al. 2007](https://doi.org/10.1016/S0140-6736%2807%2961602-X); [Morris, White and Crowther 2019](https://doi.org/10.1002/sim.8086).

## precedent

- **When:** a test or a level is proposed because others used it.
- **Default:** decide by the estimand and the design; a precedent says what others did, not why it fits this study.
  Justify each choice, the significance level included ([Lakens et al. 2018](https://doi.org/10.1038/s41562-018-0311-x)).
- **References:** [Lakens et al. 2018](https://doi.org/10.1038/s41562-018-0311-x).

## References

- Altman, D. G., and Bland, J. M. (1995). Statistics notes: absence of evidence is not evidence of absence. *BMJ*,
  311(7003), 485. [doi:10.1136/bmj.311.7003.485](https://doi.org/10.1136/bmj.311.7003.485)
- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to
  multiple testing. *Journal of the Royal Statistical Society B*, 57(1), 289–300.
  [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
- Benjamini, Y., and Yekutieli, D. (2001). The control of the false discovery rate in multiple testing under
  dependency. *The Annals of Statistics*, 29(4), 1165–1188.
  [doi:10.1214/aos/1013699998](https://doi.org/10.1214/aos/1013699998)
- Cumming, G. (2014). The new statistics: why and how. *Psychological Science*, 25(1), 7–29.
  [doi:10.1177/0956797613504966](https://doi.org/10.1177/0956797613504966)
- von Elm, E., Altman, D. G., Egger, M., Pocock, S. J., Gøtzsche, P. C., and Vandenbroucke, J. P. (2007). The
  Strengthening the Reporting of Observational Studies in Epidemiology (STROBE) statement: guidelines for reporting
  observational studies. *The Lancet*, 370(9596), 1453–1457. [doi:10.1016/S0140-6736(07)61602-X](https://doi.org/10.1016/S0140-6736%2807%2961602-X)
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*,
  6(2), 65–70. <https://www.jstor.org/stable/4615733>
- Hopewell, S., Chan, A.-W., Collins, G. S., Hróbjartsson, A., Moher, D., Schulz, K. F., et al. (2025). CONSORT 2025
  statement: updated guideline for reporting randomised trials. *BMJ*, 389, e081123.
  [doi:10.1136/bmj-2024-081123](https://doi.org/10.1136/bmj-2024-081123)
- Kahan, B. C., Hindley, J., Edwards, M., Cro, S., and Morris, T. P. (2024). The estimands framework: a primer on the
  ICH E9(R1) addendum. *BMJ*, 384, e076316. [doi:10.1136/bmj-2023-076316](https://doi.org/10.1136/bmj-2023-076316)
- Lakens, D. (2017). Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. *Social
  Psychological and Personality Science*, 8(4), 355–362. [doi:10.1177/1948550617697177](https://doi.org/10.1177/1948550617697177)
- Lakens, D., Adolfi, F. G., Albers, C. J., et al. (2018). Justify your alpha. *Nature Human Behaviour*, 2(3),
  168–171. [doi:10.1038/s41562-018-0311-x](https://doi.org/10.1038/s41562-018-0311-x)
- Lundberg, I., Johnson, R., and Stewart, B. M. (2021). What is your estimand? Defining the target quantity connects
  statistical evidence to theory. *American Sociological Review*, 86(3), 532–565.
  [doi:10.1177/00031224211004187](https://doi.org/10.1177/00031224211004187)
- Morris, T. P., White, I. R., and Crowther, M. J. (2019). Using simulation studies to evaluate statistical methods.
  *Statistics in Medicine*, 38(11), 2074–2102. [doi:10.1002/sim.8086](https://doi.org/10.1002/sim.8086)
- Nosek, B. A., Ebersole, C. R., DeHaven, A. C., and Mellor, D. T. (2018). The preregistration revolution.
  *Proceedings of the National Academy of Sciences*, 115(11), 2600–2606. [doi:10.1073/pnas.1708274114](https://doi.org/10.1073/pnas.1708274114)
- Wasserstein, R. L., and Lazar, N. A. (2016). The ASA's statement on p-values: context, process, and purpose. *The
  American Statistician*, 70(2), 129–133. [doi:10.1080/00031305.2016.1154108](https://doi.org/10.1080/00031305.2016.1154108)
- Wasserstein, R. L., Schirm, A. L., and Lazar, N. A. (2019). Moving to a world beyond "p < 0.05". *The American
  Statistician*, 73(sup1), 1–19. [doi:10.1080/00031305.2019.1583913](https://doi.org/10.1080/00031305.2019.1583913)

## Versions

- **0.1** (2026-11-13): first draft, for review by someone in the field.
- **0.2** (2026-11-13): each citation checked against the paper. The estimand entry follows the estimands
  framework (Lundberg, Johnson and Stewart 2021; Kahan et al. 2024) instead of citing a paper on simulation studies;
  CONSORT 2025 replaces CONSORT 2010; Benjamini–Hochberg states its dependence condition; the effect-size, no-difference,
  multiple-tests, preregistration and precedent entries gain the references for what they say.
