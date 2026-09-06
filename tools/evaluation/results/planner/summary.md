# Experiment A: planner forecast accuracy (frozen execution)


## Knowledge source (conversions, 1.2M, 21 d)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| history 0 | 16 | -0.1% | +5.3% | 25.7% | 48.4% | 38% |
| history 1 | 16 | -0.1% | -7.6% | 8.0% | 13.2% | 100% |
| history 3 | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |
| history 5 | 16 | -0.1% | -3.6% | 6.9% | 12.8% | 100% |

## KPI (1.2M, 21 d)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| conversions · history 0 | 16 | -0.1% | +5.3% | 25.7% | 48.4% | 38% |
| conversions · history 3 | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |
| clicks · history 0 | 16 | -0.1% | -4.8% | 30.8% | 37.4% | 25% |
| clicks · history 3 | 16 | -0.3% | -2.4% | 4.6% | 13.4% | 100% |
| unique_reach · history 0 | 16 | -0.0% | -15.5% | 15.5% | 27.0% | 50% |
| unique_reach · history 3 | 16 | -0.0% | -6.7% | 6.7% | 11.5% | 100% |

## Budget (21 d)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| conversions · 0.5M · history 0 | 16 | -0.0% | +6.7% | 19.8% | 35.5% | 50% |
| conversions · 0.5M · history 3 | 16 | -0.0% | -4.8% | 7.1% | 11.7% | 100% |
| conversions · 1.2M · history 0 | 16 | -0.1% | +5.3% | 25.7% | 48.4% | 38% |
| conversions · 1.2M · history 3 | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |
| conversions · 3.0M · history 0 | 16 | -0.6% | -5.3% | 24.1% | 39.4% | 38% |
| conversions · 3.0M · history 3 | 16 | -0.9% | +1.2% | 5.5% | 9.9% | 100% |
| clicks · 0.5M · history 0 | 16 | -0.0% | -3.8% | 33.2% | 48.1% | 25% |
| clicks · 0.5M · history 3 | 16 | -0.0% | +1.7% | 4.1% | 17.5% | 88% |
| clicks · 1.2M · history 0 | 16 | -0.1% | -4.8% | 30.8% | 37.4% | 25% |
| clicks · 1.2M · history 3 | 16 | -0.3% | -2.4% | 4.6% | 13.4% | 100% |
| clicks · 3.0M · history 0 | 16 | -6.0% | -3.0% | 24.5% | 33.8% | 38% |
| clicks · 3.0M · history 3 | 16 | -1.9% | -3.1% | 5.3% | 9.1% | 100% |

## Horizon (conversions, 1.2M)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| 14 d · history 0 | 16 | -0.0% | +8.1% | 24.7% | 49.6% | 38% |
| 14 d · history 3 | 16 | -0.1% | +0.3% | 8.7% | 12.4% | 100% |
| 21 d · history 0 | 16 | -0.1% | +5.3% | 25.7% | 48.4% | 38% |
| 21 d · history 3 | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |

## Strategy (conversions, 1.2M, 21 d)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| optimized · history 0 | 16 | -0.1% | +5.3% | 25.7% | 48.4% | 38% |
| optimized · history 3 | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |
| uniform · history 0 | 16 | -0.1% | +8.5% | 15.3% | 51.4% | 62% |
| uniform · history 3 | 16 | -0.1% | +14.7% | 14.7% | 23.7% | 81% |

## Warm-up style (conversions, 1.2M, 21 d, history 3)

| Slice | Runs | Dev spend p50 | Dev KPI p50 | |Dev KPI| p50 | |Dev KPI| p90 | Within 20% |
|---|---:|---:|---:|---:|---:|---:|
| frozen | 16 | -0.0% | -0.4% | 10.2% | 13.4% | 100% |
| uniform | 16 | -0.1% | -4.1% | 4.9% | 12.4% | 100% |

## Task B: target -> budget -> frozen execution

| Cell | History | Runs | Target hit (fact ≥ target) | Fact / target p50 | Fact / target p90 | Required budget p50 |
|---|---:|---:|---:|---:|---:|---:|
| taskB-clicks-50k-14d | 0 | 16 | 50% | 1.00 | 1.42 | 678,911 |
| taskB-clicks-50k-14d | 3 | 16 | 25% | 0.98 | 1.13 | 594,820 |
| taskB-conversions-2k-21d | 0 | 16 | 50% | 1.02 | 1.48 | 1,392,463 |
| taskB-conversions-2k-21d | 3 | 16 | 62% | 1.01 | 1.14 | 1,086,754 |

## Error decomposition per channel (conversions, 1.2M, 21 d), fact / plan medians

| History | Rows | Impressions | CTR | CR | CPM |
|---:|---:|---:|---:|---:|---:|
| 0 | 80 | 0.87 | 0.99 | 1.03 | 1.14 |
| 1 | 48 | 0.98 | 0.98 | 0.95 | 1.02 |
| 3 | 42 | 0.97 | 1.02 | 0.98 | 1.03 |
| 5 | 44 | 0.99 | 1.02 | 0.97 | 1.01 |

Dev is (fact − plan) / plan at the end of the campaign; the case threshold of 20% applies to spend and KPI at once. History N = the plan was built from N earlier campaigns on the same world seed (0 = public catalog). Task B plans the least budget for the target and then executes it frozen; fact / target > 1 means the planner reserved more budget than needed.
