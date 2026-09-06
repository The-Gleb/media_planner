# Media Planner evaluation

Budget 1,200,000, horizon 504 h, KPI `conversions`, replan every 1 h, random market events off, history levels 0, 3 (uniform warm-up campaigns), 80 runs.

## Planner: forecast accuracy under frozen execution

The approved plan is executed exactly as approved, so the deviation of the fact from the plan is the planner's forecast error. Symmetric: over-forecasting reserves money for nothing, under-forecasting hides achievable KPI.

| History | Scenario | Runs | Final dev spend p50 | Final dev KPI p50 | |Final dev KPI| p90 | Within 20% | Trajectory error KPI p50 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | none | 4 | -0.2% | +21.5% | 91.4% | 0% | 46.7% |
| 0 | ctr_drop | 4 | -0.2% | +10.5% | 75.5% | 0% | 44.4% |
| 0 | cpm_spike | 4 | -0.2% | +12.1% | 77.6% | 0% | 44.6% |
| 0 | supply_drop | 4 | -2.7% | +19.4% | 83.8% | 0% | 46.1% |
| 0 | pause | 4 | -6.9% | +14.9% | 81.8% | 0% | 43.8% |
| 3 | none | 4 | -0.3% | +12.9% | 20.7% | 75% | 11.0% |
| 3 | ctr_drop | 4 | -0.3% | +1.9% | 7.5% | 100% | 7.7% |
| 3 | cpm_spike | 4 | -0.3% | +3.5% | 8.8% | 100% | 7.9% |
| 3 | supply_drop | 4 | -4.4% | +7.8% | 15.2% | 100% | 10.4% |
| 3 | pause | 4 | -8.3% | +4.7% | 11.6% | 100% | 6.8% |

## Traffic manager: KPI delivered on the approved plan

Same plan, same world, same shock; the live mode is the only difference. KPI uplift is the fact KPI of the live mode relative to frozen execution; budget use is fact spend over the approved budget; reallocated is the share of budget moved away from approved caps; closeness is the absolute final deviation from the plan.

| History | Scenario | Live mode | Pairs | KPI uplift vs frozen p50 | More KPI than frozen | Budget use p50 | Reallocated p50 | Closeness to plan p50 | Frozen closeness p50 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | none | adaptive | 4 | +15.5% | 100% | 100.0% | 86.0% | 39.2% | 47.0% |
| 0 | ctr_drop | adaptive | 4 | +14.2% | 75% | 100.0% | 80.1% | 36.7% | 41.8% |
| 0 | cpm_spike | adaptive | 4 | +13.4% | 100% | 100.0% | 84.5% | 37.3% | 42.3% |
| 0 | supply_drop | adaptive | 4 | +16.2% | 100% | 99.9% | 88.3% | 40.4% | 46.1% |
| 0 | pause | adaptive | 4 | +19.9% | 100% | 100.0% | 84.0% | 41.1% | 43.6% |
| 3 | none | adaptive | 4 | -2.1% | 25% | 100.0% | 58.2% | 8.9% | 12.9% |
| 3 | ctr_drop | adaptive | 4 | -0.8% | 50% | 100.0% | 66.8% | 6.7% | 6.8% |
| 3 | cpm_spike | adaptive | 4 | -6.0% | 0% | 100.0% | 57.5% | 7.9% | 6.7% |
| 3 | supply_drop | adaptive | 4 | +1.8% | 75% | 100.0% | 60.6% | 9.7% | 7.8% |
| 3 | pause | adaptive | 4 | +6.2% | 75% | 100.0% | 61.7% | 9.3% | 7.0% |

Final dev is (fact − plan) / plan at the end of the campaign; the case threshold of 20% applies to its absolute value for spend and KPI at once (Within 20%). Trajectory error is the mean of |fact_t − plan_t| / plan_t over hours after the first 24 h. History N means the plan was built with the observable facts of N earlier campaigns on the same world seed; 0 is the public catalog alone. Live modes: adaptive_max maximises the remaining KPI every hour (primary live algorithm); adaptive keeps the approved channel mix while the projected finish is on plan and moves budget only to get back on plan or to spend what a paused channel cannot take (conservative variant).
