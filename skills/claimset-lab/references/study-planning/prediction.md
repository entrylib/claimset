# Prediction: forecasting, regression and classification

Version 0.1 (draft, to be reviewed by someone who works in the field) · 2026-11-13

For any study that evaluates predictions: point forecasts, quantiles, intervals or whole predictive distributions, of
time series, of a regression's outcome, or of a class.

## Principle

A prediction targets something: the mean of the outcome, its median, a quantile, the probability of a class, or the
whole distribution. Evaluate it with a scoring function that is consistent for that target, one whose expected value
is best when the prediction equals it. A measure that is consistent for a different target rewards a different
prediction from the one the method was built to make, and the comparison then says more about the measure than about
the methods (Gneiting 2011; Kolassa 2020). So the first question of an evaluation is: **what does each compared
method predict?** The measures follow from the answer.

## mean-forecasts

- **When:** the methods give point forecasts of the mean (most statistical models' point forecasts, such as ETS,
  ARIMA, TBATS and regression; most machine-learning models trained on squared error).
- **Default:** squared-error measures: RMSE. Across series on different scales, a scaled version: RMSSE (the RMSE
  scaled by the in-sample one-step naive RMSE, as in the M5 competition), or the RMSE relative to a benchmark method.
- **Why:** squared error is consistent for the mean (Gneiting 2011).
- **Avoid:** MAE and MASE as the main measure: they are consistent for the median and reward median forecasts. MAPE
  and sMAPE: they are consistent for neither; MAPE favours forecasts that are too low, and sMAPE is asymmetric and
  undefined when actual and forecast are both zero (Goodwin and Lawton 1999; Hyndman and Koehler 2006).
- **References:** Gneiting 2011; Makridakis et al. 2022; Hyndman and Koehler 2006.

## median-forecasts

- **When:** the methods give point forecasts of the median, or the study's question is about typical errors with
  equal weight for over- and under-forecasting.
- **Default:** absolute-error measures: MAE. Across series on different scales: MASE (Hyndman and Koehler 2006).
- **Why:** absolute error is consistent for the median (Gneiting 2011).
- **Avoid:** with intermittent data (many zeros), the median can be zero, and absolute-error measures then reward a
  forecast of zero for every period (Kolassa 2016). Evaluate the mean or the whole distribution as well.
- **References:** Gneiting 2011; Hyndman and Koehler 2006; Kolassa 2016.

## quantile-forecasts

- **When:** the methods give quantiles (a 90% quantile for a safety stock, several quantiles of a distribution).
- **Default:** the pinball (quantile) loss at each quantile's level, averaged over the levels when there are several;
  across series on different scales, a scaled pinball loss (as in the M5 uncertainty competition).
- **Why:** the pinball loss at level τ is consistent for the τ-quantile (Gneiting 2011).
- **References:** Gneiting 2011; Gneiting and Raftery 2007.

## prediction-intervals

- **When:** the methods give prediction intervals.
- **Default:** coverage (the share of outcomes inside the interval, against its nominal level), reported with the
  interval score, which adds the interval's width and a penalty for each miss.
- **Why:** coverage alone rewards intervals that are too wide; the interval score is a proper scoring rule for
  central intervals (Gneiting and Raftery 2007).
- **References:** Gneiting and Raftery 2007.

## distribution-forecasts

- **When:** the methods give whole predictive distributions (or many quantiles of one).
- **Default:** a proper scoring rule: CRPS, or the log score. Check calibration (the probability integral transform,
  or coverage at several levels) and report sharpness.
- **Why:** proper scoring rules are best in expectation for the true distribution; calibration and sharpness say how
  a forecast fails (Gneiting and Raftery 2007; Gneiting, Balabdaoui and Raftery 2007). For counts, see Kolassa 2016.
- **References:** Gneiting and Raftery 2007; Gneiting, Balabdaoui and Raftery 2007; Kolassa 2016.

## class-probabilities

- **When:** classifiers that give probabilities of classes.
- **Default:** a proper scoring rule: log loss, or the Brier score. Report calibration (a reliability diagram).
- **Why:** proper scoring rules reward the true probabilities (Brier 1950; Gneiting and Raftery 2007).
- **Avoid:** accuracy, unless the predictions are labels, the costs of errors are equal and the classes balanced. AUC
  measures how well cases are ranked, not whether probabilities are right, and treats costs inconsistently (Hand
  2009). With rare classes, precision and recall say more than the ROC curve (Saito and Rehmsmeier 2015).
- **References:** Brier 1950; Gneiting and Raftery 2007; Hand 2009; Saito and Rehmsmeier 2015.

## same-target

- **When:** the compared methods predict different things (one the mean, another the median).
- **Default:** evaluate each against the target it predicts, or make them predict the same target before comparing.
  Say in the claim which target the comparison is about.
- **Why:** a single measure favours the methods that target what it is consistent for (Kolassa 2020).
- **References:** Gneiting 2011; Kolassa 2020.

## many-series

- **When:** methods are compared over many series or data sets.
- **Default:** report the distribution of each method's scaled errors across series, not only their mean, and test
  the differences over series: a Friedman test with Nemenyi post-hoc comparisons (the multiple comparisons with the
  best of the M3 analysis), or paired tests on per-series differences with a correction for multiple tests. For two
  methods on one long series, the Diebold–Mariano test.
- **Why:** means over many series are dominated by a few; rank-based tests over series do not assume the errors are
  comparable across them (Demšar 2006; Koning et al. 2005).
- **References:** Demšar 2006; Koning et al. 2005; Diebold and Mariano 1995.

## precedent

- **When:** a measure is proposed because a competition or a well-known study used it ("the M4 used sMAPE and MASE").
- **Default:** decide by what the compared methods predict (the entries above). Use the precedent's measure as well
  only to compare with its published results, and say so.
- **Why:** a precedent says what others did, not why it fits this study.

## References

- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78(1),
  1–3. doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
- Demšar, J. (2006). Statistical comparisons of classifiers over multiple data sets. *Journal of Machine Learning
  Research*, 7, 1–30. https://jmlr.org/papers/v7/demsar06a.html
- Diebold, F. X., and Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business and Economic
  Statistics*, 13(3), 253–263. doi:10.1080/07350015.1995.10524599
- Gneiting, T. (2011). Making and evaluating point forecasts. *Journal of the American Statistical Association*,
  106(494), 746–762. doi:10.1198/jasa.2011.r10138
- Gneiting, T., Balabdaoui, F., and Raftery, A. E. (2007). Probabilistic forecasts, calibration and sharpness.
  *Journal of the Royal Statistical Society B*, 69(2), 243–268. doi:10.1111/j.1467-9868.2007.00587.x
- Gneiting, T., and Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the
  American Statistical Association*, 102(477), 359–378. doi:10.1198/016214506000001437
- Goodwin, P., and Lawton, R. (1999). On the asymmetry of the symmetric MAPE. *International Journal of
  Forecasting*, 15(4), 405–408. doi:10.1016/S0169-2070(99)00007-2
- Hand, D. J. (2009). Measuring classifier performance: a coherent alternative to the area under the ROC curve.
  *Machine Learning*, 77, 103–123. doi:10.1007/s10994-009-5119-5
- Hyndman, R. J., and Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal
  of Forecasting*, 22(4), 679–688. doi:10.1016/j.ijforecast.2006.03.001
- Kolassa, S. (2016). Evaluating predictive count data distributions in retail sales forecasting. *International
  Journal of Forecasting*, 32(3), 788–803. doi:10.1016/j.ijforecast.2015.12.004
- Kolassa, S. (2020). Why the "best" point forecast depends on the error or accuracy measure. *International Journal
  of Forecasting*, 36(1), 208–211. doi:10.1016/j.ijforecast.2019.02.017
- Koning, A. J., Franses, P. H., Hibon, M., and Stekler, H. O. (2005). The M3 competition: statistical tests of the
  results. *International Journal of Forecasting*, 21(3), 397–409. doi:10.1016/j.ijforecast.2004.10.003
- Makridakis, S., Spiliotis, E., and Assimakopoulos, V. (2022). M5 accuracy competition: results, findings, and
  conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. doi:10.1016/j.ijforecast.2021.11.013
- Saito, T., and Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when
  evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, 10(3), e0118432.
  doi:10.1371/journal.pone.0118432

## Versions

- **0.1** (2026-11-13): first draft, for review by someone in the field.
