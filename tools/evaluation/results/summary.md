# Media Planner evaluation: history, frozen and adaptive

Budget 1,200,000, horizon 504 h, KPI `conversions`, replan every 1 h, random market events off, history levels 0, 3 (uniform warm-up campaigns), 80 runs.

## Per history level, scenario and mode

| History | Scenario | Mode | Runs | Final dev spend p50 | Final dev KPI p50 | |Final dev KPI| p90 | Within 20% | Trajectory error spend p50 | Trajectory error KPI p50 | Reallocated p50 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | none | frozen | 4 | -0.2% | +21.5% | 91.4% | 0% | 0.4% | 46.7% | 0.0% |
| 0 | none | adaptive | 4 | -0.0% | +34.5% | 104.9% | 50% | 0.6% | 46.7% | 86.0% |
| 0 | ctr_drop | frozen | 4 | -0.2% | +10.5% | 75.5% | 0% | 0.4% | 44.4% | 0.0% |
| 0 | ctr_drop | adaptive | 4 | -0.0% | +25.5% | 92.7% | 25% | 0.6% | 45.5% | 80.1% |
| 0 | cpm_spike | frozen | 4 | -0.2% | +12.1% | 77.6% | 0% | 0.4% | 44.6% | 0.0% |
| 0 | cpm_spike | adaptive | 4 | -0.0% | +26.9% | 92.5% | 25% | 0.6% | 45.6% | 84.5% |
| 0 | supply_drop | frozen | 4 | -2.7% | +19.4% | 83.8% | 0% | 1.2% | 46.1% | 0.0% |
| 0 | supply_drop | adaptive | 4 | -0.1% | +33.1% | 104.1% | 50% | 1.3% | 47.1% | 88.3% |
| 0 | pause | frozen | 4 | -6.9% | +14.9% | 81.8% | 0% | 4.3% | 43.8% | 0.0% |
| 0 | pause | adaptive | 4 | -0.0% | +35.0% | 105.3% | 50% | 3.3% | 45.9% | 84.0% |
| 3 | none | frozen | 4 | -0.3% | +12.9% | 20.7% | 75% | 0.6% | 11.0% | 0.0% |
| 3 | none | adaptive | 4 | -0.0% | +8.9% | 15.0% | 100% | 0.4% | 12.3% | 58.2% |
| 3 | ctr_drop | frozen | 4 | -0.3% | +1.9% | 7.5% | 100% | 0.6% | 7.7% | 0.0% |
| 3 | ctr_drop | adaptive | 4 | -0.0% | +1.6% | 9.3% | 100% | 0.4% | 9.6% | 66.8% |
| 3 | cpm_spike | frozen | 4 | -0.3% | +3.5% | 8.8% | 100% | 0.6% | 7.9% | 0.0% |
| 3 | cpm_spike | adaptive | 4 | -0.0% | -3.2% | 10.7% | 100% | 0.4% | 9.8% | 57.5% |
| 3 | supply_drop | frozen | 4 | -4.4% | +7.8% | 15.2% | 100% | 1.9% | 10.4% | 0.0% |
| 3 | supply_drop | adaptive | 4 | -0.0% | +9.7% | 15.1% | 100% | 0.8% | 12.3% | 60.6% |
| 3 | pause | frozen | 4 | -8.3% | +4.7% | 11.6% | 100% | 5.4% | 6.8% | 0.0% |
| 3 | pause | adaptive | 4 | -0.0% | +9.3% | 13.9% | 100% | 4.0% | 9.5% | 61.7% |

## Cold vs warm (same seeds, shock and mode; warm − cold)

| Warm history | Scenario | Mode | Pairs | Δ |final dev KPI| p50 | Δ |final dev spend| p50 | Warm closer at the end (KPI) | Warm within 20% | Cold within 20% |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 3 | none | frozen | 4 | -35.1% | +0.1% | 100% | 75% | 0% |
| 3 | none | adaptive | 4 | -33.7% | -0.0% | 75% | 100% | 50% |
| 3 | ctr_drop | frozen | 4 | -35.0% | +0.1% | 100% | 100% | 0% |
| 3 | ctr_drop | adaptive | 4 | -30.9% | +0.0% | 75% | 100% | 25% |
| 3 | cpm_spike | frozen | 4 | -35.6% | +0.1% | 100% | 100% | 0% |
| 3 | cpm_spike | adaptive | 4 | -31.5% | +0.0% | 75% | 100% | 25% |
| 3 | supply_drop | frozen | 4 | -40.4% | +1.8% | 100% | 100% | 0% |
| 3 | supply_drop | adaptive | 4 | -34.9% | +0.0% | 75% | 100% | 50% |
| 3 | pause | frozen | 4 | -35.4% | +1.5% | 100% | 100% | 0% |
| 3 | pause | adaptive | 4 | -34.2% | +0.0% | 75% | 100% | 50% |

## Frozen vs adaptive (same seeds, shock and history; adaptive − frozen)

| History | Scenario | Pairs | Δ |final dev KPI| p50 | Δ |final dev spend| p50 | Adaptive closer at the end (KPI) | Δ trajectory error KPI p50 | Adaptive closer on trajectory (KPI) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | none | 4 | -7.8% | -0.1% | 50% | +0.9% | 50% |
| 0 | ctr_drop | 4 | -5.1% | -0.2% | 75% | +1.3% | 50% |
| 0 | cpm_spike | 4 | -5.0% | -0.2% | 50% | +1.4% | 50% |
| 0 | supply_drop | 4 | -5.8% | -2.6% | 50% | +1.6% | 50% |
| 0 | pause | 4 | -2.5% | -6.8% | 50% | +2.3% | 50% |
| 3 | none | 4 | -0.7% | -0.2% | 75% | +0.9% | 50% |
| 3 | ctr_drop | 4 | +1.5% | -0.2% | 25% | +1.4% | 25% |
| 3 | cpm_spike | 4 | +2.8% | -0.3% | 50% | +1.6% | 25% |
| 3 | supply_drop | 4 | +0.3% | -4.3% | 50% | +1.2% | 50% |
| 3 | pause | 4 | +2.2% | -8.3% | 50% | +0.7% | 50% |

Final dev is the signed deviation of the cumulative fact from the approved plan at the end of the campaign, (fact − plan) / plan; the case threshold of 20% applies to its absolute value for spend and KPI at once (column Within 20%). Trajectory error is the mean of |fact_t − plan_t| / plan_t over hours after the first 24 h. History N means the plan was built with the observable facts of N earlier campaigns on the same world seed; 0 is the public catalog alone. Reallocated is the share of the budget moved away from approved caps.
