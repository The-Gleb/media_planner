# Media Planner evaluation: history, frozen and adaptive

Budget 1,200,000, horizon 504 h, KPI `conversions`, replan every 1 h, random market events off, history levels 3 (frozen warm-up campaigns), 60 runs.

## Per history level, scenario and mode

| History | Scenario | Mode | Runs | Final dev spend p50 | Final dev KPI p50 | |Final dev KPI| p90 | Within 20% | Trajectory error spend p50 | Trajectory error KPI p50 | Reallocated p50 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | none | frozen | 4 | -0.1% | +3.6% | 6.4% | 100% | 0.9% | 3.7% | 0.0% |
| 3 | none | adaptive | 4 | -0.0% | +3.8% | 7.8% | 100% | 0.5% | 3.8% | 2.1% |
| 3 | none | adaptive_max | 4 | -0.0% | +4.6% | 9.0% | 100% | 0.6% | 4.7% | 31.6% |
| 3 | ctr_drop | frozen | 4 | -0.1% | -8.2% | 9.5% | 100% | 0.9% | 4.8% | 0.0% |
| 3 | ctr_drop | adaptive | 4 | -0.0% | -4.7% | 4.9% | 100% | 0.6% | 3.9% | 28.7% |
| 3 | ctr_drop | adaptive_max | 4 | -0.0% | -3.2% | 4.9% | 100% | 0.6% | 3.6% | 38.1% |
| 3 | cpm_spike | frozen | 4 | -0.1% | -6.6% | 7.9% | 100% | 0.9% | 4.4% | 0.0% |
| 3 | cpm_spike | adaptive | 4 | -0.0% | -3.7% | 4.5% | 100% | 0.6% | 3.5% | 25.4% |
| 3 | cpm_spike | adaptive_max | 4 | -0.0% | -3.1% | 4.2% | 100% | 0.5% | 3.4% | 37.3% |
| 3 | supply_drop | frozen | 4 | -6.0% | -2.9% | 7.3% | 100% | 3.0% | 4.8% | 0.0% |
| 3 | supply_drop | adaptive | 4 | -0.0% | +2.4% | 5.3% | 100% | 1.1% | 3.9% | 12.2% |
| 3 | supply_drop | adaptive_max | 4 | -0.0% | +4.0% | 5.8% | 100% | 0.7% | 4.6% | 38.4% |
| 3 | pause | frozen | 4 | -9.5% | -4.4% | 6.6% | 100% | 6.5% | 5.5% | 0.0% |
| 3 | pause | adaptive | 4 | -0.0% | +2.6% | 6.8% | 100% | 1.2% | 2.9% | 34.9% |
| 3 | pause | adaptive_max | 4 | -0.0% | +2.9% | 6.9% | 100% | 0.7% | 3.0% | 40.8% |

## Cold vs warm (same seeds, shock and mode; warm − cold)

| Warm history | Scenario | Mode | Pairs | Δ |final dev KPI| p50 | Δ |final dev spend| p50 | Warm closer at the end (KPI) | Warm within 20% | Cold within 20% |
|---:|---|---|---:|---:|---:|---:|---:|---:|

## Frozen vs adaptive (same seeds, shock and history; adaptive − frozen)

| History | Scenario | Adaptive kind | Pairs | Δ |final dev KPI| p50 | Δ KPI shortfall p50 | Δ |final dev spend| p50 | Adaptive closer at the end (KPI) | Δ trajectory error KPI p50 |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 3 | none | adaptive | 4 | +0.3% | +0.0% | -0.1% | 25% | +0.2% |
| 3 | none | adaptive_max | 4 | +1.5% | +0.0% | -0.1% | 25% | +0.7% |
| 3 | ctr_drop | adaptive | 4 | -3.6% | -3.6% | -0.0% | 100% | -0.6% |
| 3 | ctr_drop | adaptive_max | 4 | -3.6% | -3.6% | -0.1% | 100% | -0.5% |
| 3 | cpm_spike | adaptive | 4 | -2.9% | -2.9% | -0.1% | 100% | -0.6% |
| 3 | cpm_spike | adaptive_max | 4 | -3.1% | -3.1% | -0.1% | 100% | -0.4% |
| 3 | supply_drop | adaptive | 4 | -2.1% | -3.1% | -5.5% | 75% | +0.0% |
| 3 | supply_drop | adaptive_max | 4 | -1.5% | -3.4% | -6.0% | 50% | +0.3% |
| 3 | pause | adaptive | 4 | -1.6% | -4.4% | -9.2% | 50% | -2.3% |
| 3 | pause | adaptive_max | 4 | -1.3% | -4.4% | -9.1% | 50% | -2.1% |

Final dev is the signed deviation of the cumulative fact from the approved plan at the end of the campaign, (fact − plan) / plan; the case threshold of 20% applies to its absolute value for spend and KPI at once (column Within 20%). Trajectory error is the mean of |fact_t − plan_t| / plan_t over hours after the first 24 h. History N means the plan was built with the observable facts of N earlier campaigns on the same world seed; 0 is the public catalog alone. Reallocated is the share of the budget moved away from approved caps. Mode adaptive tracks the approved plan (moves budget only when the projected finish leaves the plan); adaptive_max is the earlier behaviour that maximises the remaining KPI every hour. KPI shortfall counts only underdelivery.
