# Frozen vs adaptive evaluation

Budget 1,200,000, horizon 504 h, KPI `conversions`, replan every 1 h, random market events off, 30 runs.

Approved plan: expected spend 1,200,000, expected conversions 1,551.

## Per scenario and mode

| Scenario | Mode | Runs | MAPE spend p50 | MAPE spend p90 | MAPE KPI p50 | MAPE KPI p90 | Final dev spend p50 | Final dev KPI p50 | Within 20% | Reallocated p50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | frozen | 3 | 0.1% | 0.6% | 57.4% | 92.7% | -0.1% | +61.8% | 0% | 0.0% |
| none | adaptive | 3 | 0.4% | 1.7% | 83.5% | 117.0% | -0.0% | +58.3% | 33% | 91.1% |
| ctr_drop | frozen | 3 | 0.1% | 0.6% | 52.3% | 88.1% | -0.1% | +44.9% | 0% | 0.0% |
| ctr_drop | adaptive | 3 | 0.4% | 1.7% | 79.9% | 113.7% | -0.0% | +48.0% | 33% | 93.7% |
| cpm_spike | frozen | 3 | 0.1% | 0.6% | 53.1% | 88.7% | -0.1% | +47.8% | 0% | 0.0% |
| cpm_spike | adaptive | 3 | 0.4% | 1.6% | 80.3% | 113.5% | -0.0% | +49.8% | 33% | 91.7% |
| supply_drop | frozen | 3 | 0.4% | 1.1% | 57.2% | 91.8% | -1.0% | +61.4% | 0% | 0.0% |
| supply_drop | adaptive | 3 | 0.7% | 3.2% | 83.6% | 116.7% | -0.1% | +58.5% | 33% | 91.6% |
| pause | frozen | 3 | 3.0% | 3.5% | 51.2% | 87.3% | -5.2% | +51.9% | 0% | 0.0% |
| pause | adaptive | 3 | 2.6% | 4.6% | 80.5% | 113.8% | -0.0% | +59.4% | 33% | 91.5% |

## Paired comparison (same seeds and shock)

| Scenario | Pairs | Δ MAPE KPI p50 (adaptive − frozen) | Δ MAPE spend p50 | Adaptive closer on KPI | Adaptive closer on spend |
|---|---:|---:|---:|---:|---:|
| none | 3 | +23.9% | +0.3% | 33% | 33% |
| ctr_drop | 3 | +25.1% | +0.3% | 33% | 33% |
| cpm_spike | 3 | +24.2% | +0.3% | 33% | 33% |
| supply_drop | 3 | +24.4% | +0.3% | 33% | 33% |
| pause | 3 | +25.7% | -0.3% | 33% | 67% |

MAPE is the mean absolute percentage error of the cumulative fact against the cumulative approved-plan trajectory over all hours; final dev is the signed deviation at the end of the campaign; reallocated is the share of the budget moved away from approved caps.
