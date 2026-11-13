# Experiments and inference

Version 0.1 (draft, to be reviewed by someone who works in the field) · 2026-11-13

For studies that compare conditions, methods or groups, or estimate an effect: designed experiments, simulation
studies, observational comparisons and causal questions.

## Principle

A conclusion rests on what is estimated and how the comparison was decided. Say first what quantity the claim is
about (the estimand: which effect, on whom, compared with what), then choose the design and the analysis that estimate
it, and fix both before the data are seen. The analysis answers the question the design was built for, not the one
that turned out convenient.

## estimand

- **When:** any comparison or effect.
- **Default:** state the estimand before the design: the quantity (a difference in means, a ratio, a share), the
  population or cases, the conditions compared, and how missing or excluded units are handled.
- **Why:** without it, the same data support several different claims, and the analysis can be chosen after the
  fact.
- **References:** Morris, White and Crowther 2019 (for simulation studies: aims, data-generating mechanisms,
  estimands, methods, performance measures).

## effect-sizes

- **When:** reporting any comparison.
- **Default:** report the size of the effect with its interval, not only whether a test rejected.
- **Why:** a p-value says neither how large an effect is nor how important; an estimate with its interval does
  (Wasserstein and Lazar 2016; Cumming 2014).
- **Avoid:** "significant" or "not significant" as the finding.
- **References:** Wasserstein and Lazar 2016; Cumming 2014.

## no-difference

- **When:** the claim is that there is no difference, or no meaningful one.
- **Default:** an equivalence test against bounds fixed in advance (the smallest difference that would matter).
- **Why:** failing to reject a null hypothesis is not evidence of no difference (Lakens 2017).
- **References:** Lakens 2017.

## multiple-tests

- **When:** several tests decide the claims of one study.
- **Default:** fix the correction in advance: Holm's procedure to control the family-wise error rate, or
  Benjamini–Hochberg to control the false discovery rate when many tests screen for effects.
- **References:** Holm 1979; Benjamini and Hochberg 1995.

## simulation-studies

- **When:** methods are evaluated on simulated data.
- **Default:** plan by aims, data-generating mechanisms, estimands, methods and performance measures; choose the
  number of repetitions for the Monte Carlo error you can accept, and report that error with each result.
- **References:** Morris, White and Crowther 2019.

## preregistration

- **When:** any test meant to be confirmatory.
- **Default:** fix the hypotheses, design, analysis and decision rules before the data are seen, in a record with a
  trustworthy time (in a claimset lab, the plan).
- **References:** Nosek et al. 2018.

## reporting

- **Default:** follow the field's reporting guideline: CONSORT for randomised trials, STROBE for observational
  studies, and others at the EQUATOR Network (https://www.equator-network.org).
- **References:** Schulz, Altman and Moher 2010; von Elm et al. 2007.

## precedent

- **When:** a test or a level is proposed because others used it.
- **Default:** decide by the estimand and the design; a precedent says what others did, not why it fits this study.

## References

- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to
  multiple testing. *Journal of the Royal Statistical Society B*, 57(1), 289–300.
  doi:10.1111/j.2517-6161.1995.tb02031.x
- Cumming, G. (2014). The new statistics: why and how. *Psychological Science*, 25(1), 7–29.
  doi:10.1177/0956797613504966
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*,
  6(2), 65–70. https://www.jstor.org/stable/4615733
- Lakens, D. (2017). Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. *Social
  Psychological and Personality Science*, 8(4), 355–362. doi:10.1177/1948550617697177
- Morris, T. P., White, I. R., and Crowther, M. J. (2019). Using simulation studies to evaluate statistical methods.
  *Statistics in Medicine*, 38(11), 2074–2102. doi:10.1002/sim.8086
- Nosek, B. A., Ebersole, C. R., DeHaven, A. C., and Mellor, D. T. (2018). The preregistration revolution.
  *Proceedings of the National Academy of Sciences*, 115(11), 2600–2606. doi:10.1073/pnas.1708274114
- Schulz, K. F., Altman, D. G., and Moher, D. (2010). CONSORT 2010 statement: updated guidelines for reporting
  parallel group randomised trials. *BMJ*, 340, c332. doi:10.1136/bmj.c332
- von Elm, E., Altman, D. G., Egger, M., Pocock, S. J., Gøtzsche, P. C., and Vandenbroucke, J. P. (2007). The
  Strengthening the Reporting of Observational Studies in Epidemiology (STROBE) statement: guidelines for reporting
  observational studies. *The Lancet*, 370(9596), 1453–1457. doi:10.1016/S0140-6736(07)61602-X
- Wasserstein, R. L., and Lazar, N. A. (2016). The ASA statement on p-values: context, process, and purpose. *The
  American Statistician*, 70(2), 129–133. doi:10.1080/00031305.2016.1154108

## Versions

- **0.1** (2026-11-13): first draft, for review by someone in the field.
