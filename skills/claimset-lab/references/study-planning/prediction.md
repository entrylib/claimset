# Prediction: forecasting, regression and classification

Version 0.4 (draft, to be reviewed by someone who works in the field) · 2026-11-13

For any study that evaluates predictions: point forecasts, quantiles, intervals or whole predictive distributions, of
time series, of a regression's outcome, or of a class.

## Principle

A prediction targets something: the mean of the outcome, its median, a quantile, the probability of a class, or the
whole distribution. Evaluate it with a scoring function that is consistent for that target, one whose expected value
is best when the prediction equals it. A measure that is consistent for a different target rewards a different
prediction from the one the method was built to make, and the comparison then says more about the measure than about
the methods ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Kolassa 2020](https://doi.org/10.1016/j.ijforecast.2019.02.017)). So the first question of an evaluation is: **what does each compared
method predict?** The measures follow from the answer.

## mean-forecasts

- **When:** the methods give point forecasts of the mean. Check what each implementation returns: the point forecasts
  of ETS models are conditional means except, beyond one step ahead, with a multiplicative trend or seasonality
  ([Hyndman and Khandakar 2008](https://doi.org/10.18637/jss.v027.i03)); forecasts made on a Box-Cox or log scale and back-transformed are medians unless they are bias-adjusted
  ([Hyndman and Athanasopoulos 2018](https://otexts.com/fpp2/transformations.html)), as in TBATS or ARIMA on a transformed series; models trained on squared error give means.
- **Default:** squared-error measures: RMSE. Across series on different scales, a scaled version: RMSSE (the RMSE
  scaled by the in-sample one-step naive RMSE, as in the M5 competition; [M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf); [Makridakis, Spiliotis and Assimakopoulos 2022a](https://doi.org/10.1016/j.ijforecast.2021.11.013)), or the RMSE relative to a
  benchmark method (see [aggregation](#aggregation)).
- **Why:** squared error is consistent for the mean ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)).
- **Avoid:** MAE and MASE as the main measure: they are consistent for the median and reward median forecasts
  ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)). MAPE: it is consistent for the median of order −1, which lies below the median for positive outcomes, so
  it rewards forecasts that are too low ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)). sMAPE: for the same outcome it penalises low forecasts more heavily than high ones, so it
  rewards forecasts that are too high ([Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001); [Goodwin and Lawton 1999](https://doi.org/10.1016/S0169-2070%2899%2900007-2)), and it is undefined when actual and forecast are both zero.
- **References:** [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf); [Makridakis, Spiliotis and Assimakopoulos 2022a](https://doi.org/10.1016/j.ijforecast.2021.11.013); [Goodwin and Lawton 1999](https://doi.org/10.1016/S0169-2070%2899%2900007-2); [Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001); [Hyndman and Khandakar 2008](https://doi.org/10.18637/jss.v027.i03); [Hyndman and Athanasopoulos 2018](https://otexts.com/fpp2/transformations.html).

## median-forecasts

- **When:** the methods give point forecasts of the median (including back-transformed forecasts without bias
  adjustment), or the study's question is about typical errors with equal weight for over- and under-forecasting.
- **Default:** absolute-error measures: MAE. Across series on different scales: MASE ([Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001)).
- **Why:** absolute error is consistent for the median ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)).
- **Avoid:** with intermittent data (many zeros), the median can be zero, and absolute-error measures then reward a
  forecast of zero for every period ([Kolassa 2016](https://doi.org/10.1016/j.ijforecast.2015.12.004)); the M5 competition chose a squared-error measure for this reason
  ([Makridakis, Spiliotis and Assimakopoulos 2022a](https://doi.org/10.1016/j.ijforecast.2021.11.013)). Evaluate the mean or the whole distribution as well.
- **References:** [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001); [Kolassa 2016](https://doi.org/10.1016/j.ijforecast.2015.12.004); [Makridakis, Spiliotis and Assimakopoulos 2022a](https://doi.org/10.1016/j.ijforecast.2021.11.013).

## quantile-forecasts

- **When:** the methods give quantiles (a 90% quantile for a safety stock, several quantiles of a distribution).
- **Default:** the pinball (quantile) loss at each quantile's level, averaged over the levels when there are several.
  Across series on different scales, the scaled pinball loss: each series' pinball loss divided by the in-sample mean
  absolute error of its one-step naive forecast, as in the M5 uncertainty competition ([M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf); [Makridakis et al. 2022b](https://doi.org/10.1016/j.ijforecast.2021.10.009)), then
  averaged over the series (see [aggregation](#aggregation)).
- **Why:** the pinball loss at level τ is consistent for the τ-quantile ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)).
- **References:** [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437); [M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf); [Makridakis et al. 2022b](https://doi.org/10.1016/j.ijforecast.2021.10.009).

## prediction-intervals

- **When:** the methods give prediction intervals.
- **Default:** coverage (the share of outcomes inside the interval, against its nominal level), reported with the
  interval score, which adds the interval's width and a penalty for each miss. Across series on different scales, a
  scaled interval score: each series' interval score scaled by a quantity of that series, then averaged over the series,
  as the mean scaled interval score (MSIS) of the M4 competition does ([Makridakis, Spiliotis and Assimakopoulos 2020](https://doi.org/10.1016/j.ijforecast.2019.04.014); see [aggregation](#aggregation)).
- **Why:** coverage alone says nothing about width: intervals that are sharp and intervals that are needlessly wide
  can reach the same coverage. The interval score is a proper scoring rule for central intervals ([Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437)).
- **References:** [Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437); [Makridakis, Spiliotis and Assimakopoulos 2020](https://doi.org/10.1016/j.ijforecast.2019.04.014).

## distribution-forecasts

- **When:** the methods give whole predictive distributions (or many quantiles of one).
- **Default:** a proper scoring rule: CRPS, or the log score. Check calibration (the probability integral transform,
  or coverage at several levels) and report sharpness.
- **Why:** proper scoring rules are best in expectation for the true distribution; calibration and sharpness say how
  a forecast fails ([Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437); [Gneiting, Balabdaoui and Raftery 2007](https://doi.org/10.1111/j.1467-9868.2007.00587.x)). For counts, see [Kolassa 2016](https://doi.org/10.1016/j.ijforecast.2015.12.004).
- **References:** [Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437); [Gneiting, Balabdaoui and Raftery 2007](https://doi.org/10.1111/j.1467-9868.2007.00587.x); [Kolassa 2016](https://doi.org/10.1016/j.ijforecast.2015.12.004).

## class-probabilities

- **When:** classifiers that give probabilities of classes.
- **Default:** a proper scoring rule: log loss, or the Brier score. Report calibration (a reliability diagram).
- **Why:** proper scoring rules reward the true probabilities ([Brier 1950](https://doi.org/10.1175/1520-0493%281950%29078%3C0001:VOFEIT%3E2.0.CO;2); [Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437)).
- **Avoid:** accuracy, unless the predictions are labels, the costs of errors are equal and the classes balanced. AUC,
  which measures how well cases are ranked, not whether the probabilities are right; it also weighs the costs of
  errors differently for different classifiers ([Hand 2009](https://doi.org/10.1007/s10994-009-5119-5)). With rare classes, the precision-recall curve can say more
  than the ROC curve ([Saito and Rehmsmeier 2015](https://doi.org/10.1371/journal.pone.0118432)).
- **References:** [Brier 1950](https://doi.org/10.1175/1520-0493%281950%29078%3C0001:VOFEIT%3E2.0.CO;2); [Gneiting and Raftery 2007](https://doi.org/10.1198/016214506000001437); [Hand 2009](https://doi.org/10.1007/s10994-009-5119-5); [Saito and Rehmsmeier 2015](https://doi.org/10.1371/journal.pone.0118432).

## same-target

- **When:** the compared methods predict different things (one the mean, another the median).
- **Default:** evaluate each against the target it predicts, or make them predict the same target before comparing.
  Say in the claim which target the comparison is about.
- **Why:** different error measures are minimised by different summaries of the same predictive distribution, so a
  single measure favours the methods that target what it is consistent for ([Kolassa 2020](https://doi.org/10.1016/j.ijforecast.2019.02.017); [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138)).
- **References:** [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Kolassa 2020](https://doi.org/10.1016/j.ijforecast.2019.02.017).

## aggregation

- **When:** accuracy is summarised over several series or data sets on different scales, for point forecasts,
  quantiles or intervals.
- **Default:** scale the errors of each series by a quantity of that series that does not depend on the compared
  forecasts (the in-sample error of a naive forecast, or the error of a benchmark method), and only then average them
  over the series. Keep the measure that fits what the forecasts target, scaled: RMSSE for means, MASE for medians, the
  scaled pinball loss for quantiles, a scaled interval score (MSIS) for intervals.
- **Why:** scale-dependent measures should not be compared across data sets on different scales, and scaled errors
  make series comparable ([Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001)). A scaled measure "can be effectively used to compare forecasts across series with
  different scales" ([M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf)). Dividing by a quantity that does not depend on the forecasts keeps the measure's target.
- **Avoid:** summing or averaging RMSE, MAE, pinball losses or interval scores over series as they are: the series
  with the largest values dominate the result ([Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001); [Athanasopoulos and Kourentzes 2023](https://doi.org/10.1016/j.ijforecast.2022.08.003)).
- **References:** [Hyndman and Koehler 2006](https://doi.org/10.1016/j.ijforecast.2006.03.001); [Athanasopoulos and Kourentzes 2023](https://doi.org/10.1016/j.ijforecast.2022.08.003); [M5 guide 2020](https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf); [Makridakis, Spiliotis and Assimakopoulos 2022a](https://doi.org/10.1016/j.ijforecast.2021.11.013); [Makridakis et al. 2022b](https://doi.org/10.1016/j.ijforecast.2021.10.009); [Makridakis, Spiliotis and Assimakopoulos 2020](https://doi.org/10.1016/j.ijforecast.2019.04.014).

## many-series

- **When:** methods are compared over many series or data sets.
- **Default:** summarise each method's accuracy over the series by aggregates of a scaled measure (see
  [aggregation](#aggregation)): its mean, together with its median and quartiles. To tell whether methods whose
  aggregates are close differ significantly, test their ranks on each series: a Friedman test with Nemenyi post-hoc
  comparisons ([Demšar 2006](https://jmlr.org/papers/v7/demsar06a.html)), or multiple comparisons with the best (MCB), as in the statistical analysis of the M3
  competition ([Koning et al. 2005](https://doi.org/10.1016/j.ijforecast.2004.10.003)). For two methods on one long series, the Diebold–Mariano test ([Diebold and Mariano 1995](https://doi.org/10.1080/07350015.1995.10524599)).
- **Why:** a mean over many series is sensitive to a few outlying ones ([Demšar 2006](https://jmlr.org/papers/v7/demsar06a.html)), and the median and quartiles show what
  it hides. When methods perform very similarly, their aggregates cannot say whether the difference is more than
  chance; rank-based tests can, and they do not assume the errors are comparable across series ([Demšar 2006](https://jmlr.org/papers/v7/demsar06a.html)).
- **References:** [Demšar 2006](https://jmlr.org/papers/v7/demsar06a.html); [Koning et al. 2005](https://doi.org/10.1016/j.ijforecast.2004.10.003); [Diebold and Mariano 1995](https://doi.org/10.1080/07350015.1995.10524599).

## precedent

- **When:** a measure is proposed because a competition or a well-known study used it ("the M4 used sMAPE and MASE").
- **Default:** decide by what the compared methods predict (the entries above). Use the precedent's measure as well
  only to compare with its published results, and say so.
- **Why:** a precedent says what others did, not why it fits this study; the measure has to be consistent for what
  the methods predict ([Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Kolassa 2020](https://doi.org/10.1016/j.ijforecast.2019.02.017)).
- **References:** [Gneiting 2011](https://doi.org/10.1198/jasa.2011.r10138); [Kolassa 2020](https://doi.org/10.1016/j.ijforecast.2019.02.017).

## References

- Athanasopoulos, G., and Kourentzes, N. (2023). On the evaluation of hierarchical forecasts. *International Journal
  of Forecasting*, 39(4), 1502–1511. [doi:10.1016/j.ijforecast.2022.08.003](https://doi.org/10.1016/j.ijforecast.2022.08.003)
- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78(1),
  1–3. [doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2](https://doi.org/10.1175/1520-0493%281950%29078%3C0001:VOFEIT%3E2.0.CO;2)
- Demšar, J. (2006). Statistical comparisons of classifiers over multiple data sets. *Journal of Machine Learning
  Research*, 7, 1–30. <https://jmlr.org/papers/v7/demsar06a.html>
- Diebold, F. X., and Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business and Economic
  Statistics*, 13(3), 253–263. [doi:10.1080/07350015.1995.10524599](https://doi.org/10.1080/07350015.1995.10524599)
- Gneiting, T., Balabdaoui, F., and Raftery, A. E. (2007). Probabilistic forecasts, calibration and sharpness.
  *Journal of the Royal Statistical Society B*, 69(2), 243–268. [doi:10.1111/j.1467-9868.2007.00587.x](https://doi.org/10.1111/j.1467-9868.2007.00587.x)
- Gneiting, T., and Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the
  American Statistical Association*, 102(477), 359–378. [doi:10.1198/016214506000001437](https://doi.org/10.1198/016214506000001437)
- Gneiting, T. (2011). Making and evaluating point forecasts. *Journal of the American Statistical Association*,
  106(494), 746–762. [doi:10.1198/jasa.2011.r10138](https://doi.org/10.1198/jasa.2011.r10138)
- Goodwin, P., and Lawton, R. (1999). On the asymmetry of the symmetric MAPE. *International Journal of
  Forecasting*, 15(4), 405–408. [doi:10.1016/S0169-2070(99)00007-2](https://doi.org/10.1016/S0169-2070%2899%2900007-2)
- Hand, D. J. (2009). Measuring classifier performance: a coherent alternative to the area under the ROC curve.
  *Machine Learning*, 77(1), 103–123. [doi:10.1007/s10994-009-5119-5](https://doi.org/10.1007/s10994-009-5119-5)
- Hyndman, R. J., and Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal
  of Forecasting*, 22(4), 679–688. [doi:10.1016/j.ijforecast.2006.03.001](https://doi.org/10.1016/j.ijforecast.2006.03.001)
- Hyndman, R. J., and Khandakar, Y. (2008). Automatic time series forecasting: the forecast package for R. *Journal of
  Statistical Software*, 27(3), 1–22. [doi:10.18637/jss.v027.i03](https://doi.org/10.18637/jss.v027.i03)
- Hyndman, R. J., and Athanasopoulos, G. (2018). *Forecasting: principles and practice* (2nd ed.), section 3.2,
  Transformations and adjustments. OTexts. <https://otexts.com/fpp2/transformations.html>
- Kolassa, S. (2016). Evaluating predictive count data distributions in retail sales forecasting. *International
  Journal of Forecasting*, 32(3), 788–803. [doi:10.1016/j.ijforecast.2015.12.004](https://doi.org/10.1016/j.ijforecast.2015.12.004)
- Kolassa, S. (2020). Why the "best" point forecast depends on the error or accuracy measure. *International Journal
  of Forecasting*, 36(1), 208–211. [doi:10.1016/j.ijforecast.2019.02.017](https://doi.org/10.1016/j.ijforecast.2019.02.017)
- Koning, A. J., Franses, P. H., Hibon, M., and Stekler, H. O. (2005). The M3 competition: statistical tests of the
  results. *International Journal of Forecasting*, 21(3), 397–409. [doi:10.1016/j.ijforecast.2004.10.003](https://doi.org/10.1016/j.ijforecast.2004.10.003)
- M Open Forecasting Center (2020). *The M5 competition: competitors' guide*.
  <https://github.com/Mcompetitions/M5-methods/blob/master/M5-Competitors-Guide.pdf>
- Makridakis, S., Spiliotis, E., and Assimakopoulos, V. (2020). The M4 Competition: 100,000 time series and 61
  forecasting methods. *International Journal of Forecasting*, 36(1), 54–74. [doi:10.1016/j.ijforecast.2019.04.014](https://doi.org/10.1016/j.ijforecast.2019.04.014)
- Makridakis, S., Spiliotis, E., and Assimakopoulos, V. (2022a). M5 accuracy competition: results, findings, and
  conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. [doi:10.1016/j.ijforecast.2021.11.013](https://doi.org/10.1016/j.ijforecast.2021.11.013)
- Makridakis, S., Spiliotis, E., Assimakopoulos, V., Chen, Z., Gaba, A., Tsetlin, I., and Winkler, R. L. (2022b). The M5
  uncertainty competition: results, findings and conclusions. *International Journal of Forecasting*, 38(4),
  1365–1385. [doi:10.1016/j.ijforecast.2021.10.009](https://doi.org/10.1016/j.ijforecast.2021.10.009)
- Saito, T., and Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when
  evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, 10(3), e0118432.
  [doi:10.1371/journal.pone.0118432](https://doi.org/10.1371/journal.pone.0118432)

## Versions

- **0.1** (2026-11-13): first draft, for review by someone in the field.
- **0.2** (2026-11-13): each citation checked against the paper. MAPE's bias rests on Gneiting 2011 (Hyndman and
  Koehler 2006 state its direction the other way, which Hyndman later corrected); mean forecasts say which models'
  point forecasts are medians (multiplicative ETS beyond one step, back-transformed forecasts as in TBATS); the M5
  papers are cited where their measures are named; the interval, AUC, precision-recall and many-series wording
  follows what the papers say.
- **0.3** (2026-11-13): sMAPE rewards forecasts that are too high (Hyndman and Koehler 2006); a new entry,
  aggregation: scale each series' errors before averaging over series on different scales, never sum them unscaled.
- **0.4** (2026-11-13): errors of series on different scales are scaled per series before they are averaged, for
  quantiles and intervals too (the scaled pinball loss of the M5 competitors' guide; the scaled interval score of the
  M4 competition); many series: aggregates of a scaled measure (mean, median and quartiles) summarise accuracy, and
  rank tests tell whether methods that perform similarly differ. The M4 paper was checked by its record and by
  others' accounts of it only: its full text could not be reached.
