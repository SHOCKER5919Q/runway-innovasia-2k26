# How much ledger history RUNWAY needs

**Short answer:** start with **8 weeks (2 months)** of bank data; the full
feature set needs **6 months**; **12 months** covers a full seasonal cycle
and gives the forecast-accuracy track record something to measure.

## What each model needs (from the code)

| Feature | Switches on at | Full strength |
|---|---|---|
| Sales run-rate (invoices, or bank receipts if no invoices) | 4 complete weeks | 12 weeks (12-week median, 26-week lookback) |
| Recurring costs | any history (now averaged over the history that exists) | 26 weeks (180-day window) |
| Invoice-level payment-date model (ML) | 60 settled invoices | more = tighter bands |
| Customer reliability score | 3 settled invoices per customer | — |
| Customers-pay-late-together correlation | 6 months | — |
| Demand/payment-delay coupling | 6 settled months | 15 months |
| Unusual amount alerts | 12 transactions per category | — |
| Weekly spike alerts | 16 weeks | — |
| ML outlier scan | 80 transactions | — |

Seasonality comes from the industry profile, so it works from day one but
does not learn the business's own pattern.

## Measured on real data

`data/real/uci_online_retail_ii/history_experiment.py`: for every Monday
4 Apr – 7 Nov 2011, forecast the next 4 weeks of sales from only the last H
weeks of the real UCI ledger, and compare with what arrived.

| History | Forecasts | Mean error | Median | 90th percentile |
|---|---|---|---|---|
| 4 weeks | 28 | 14.5% | 14.4% | 28.8% |
| 6 weeks | 32 | 14.5% | 13.0% | 25.6% |
| 8 weeks | 32 | 14.7% | 13.6% | 25.3% |
| 13 weeks | 32 | 15.5% | 14.6% | 26.7% |
| 26 / 52 weeks | 32 | 15.5% | 14.6% | 26.7% |

Sales forecasting stops improving after ~6–8 weeks, because the estimator
uses the last 12 weeks by design; 4 weeks has the worst bad-case error.
Longer history pays off in the other models in the table above. One
dataset, one business - treat the numbers as indicative.

**Bug fixed while measuring:** recurring costs were divided by 26 weeks even
for a 2-month ledger, understating weekly costs about 3x for young
businesses. They are now averaged over the history that exists.
