# Media Planner evaluation

Budget 1,200,000, horizon 504 h, KPI `conversions`, replan every 1 h, random market events off, history levels 3 (frozen warm-up campaigns), 60 runs.

## Planner: forecast accuracy under frozen execution

The approved plan is executed exactly as approved, so the deviation of the fact from the plan is the planner's forecast error. Symmetric: over-forecasting reserves money for nothing, under-forecasting hides achievable KPI.

| History | Scenario | Runs | Final dev spend p50 | Final dev KPI p50 | |Final dev KPI| p90 | Within 20% | Trajectory error KPI p50 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 3 | none | 4 | -0.1% | +3.6% | 6.4% | 100% | 3.7% |
| 3 | ctr_drop | 4 | -0.1% | -8.2% | 9.5% | 100% | 4.8% |
| 3 | cpm_spike | 4 | -0.1% | -6.6% | 7.9% | 100% | 4.4% |
| 3 | supply_drop | 4 | -6.0% | -2.9% | 7.3% | 100% | 4.8% |
| 3 | pause | 4 | -9.5% | -4.4% | 6.6% | 100% | 5.5% |

## Traffic manager: KPI delivered on the approved plan

Same plan, same world, same shock; the live mode is the only difference. KPI uplift is the fact KPI of the live mode relative to frozen execution; budget use is fact spend over the approved budget; reallocated is the share of budget moved away from approved caps; closeness is the absolute final deviation from the plan.

| History | Scenario | Live mode | Pairs | KPI uplift vs frozen p50 | More KPI than frozen | Budget use p50 | Reallocated p50 | Closeness to plan p50 | Frozen closeness p50 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | none | adaptive | 4 | +0.3% | 75% | 100.0% | 2.1% | 3.8% | 3.6% |
| 3 | none | adaptive_max | 4 | +1.4% | 75% | 100.0% | 31.6% | 4.6% | 3.6% |
| 3 | ctr_drop | adaptive | 4 | +3.9% | 100% | 100.0% | 28.7% | 4.7% | 8.2% |
| 3 | ctr_drop | adaptive_max | 4 | +3.9% | 100% | 100.0% | 38.1% | 3.2% | 8.2% |
| 3 | cpm_spike | adaptive | 4 | +3.1% | 100% | 100.0% | 25.4% | 3.7% | 6.6% |
| 3 | cpm_spike | adaptive_max | 4 | +3.3% | 100% | 100.0% | 37.3% | 3.1% | 6.6% |
| 3 | supply_drop | adaptive | 4 | +3.5% | 75% | 99.5% | 12.2% | 2.4% | 6.6% |
| 3 | supply_drop | adaptive_max | 4 | +5.1% | 100% | 100.0% | 38.4% | 4.0% | 6.6% |
| 3 | pause | adaptive | 4 | +7.6% | 100% | 99.7% | 34.9% | 2.6% | 4.4% |
| 3 | pause | adaptive_max | 4 | +8.4% | 100% | 100.0% | 40.8% | 2.9% | 4.4% |

## Live modes head to head (same seeds, shock and history)

| History | Scenario | Pairs | adaptive KPI p50 | adaptive_max KPI p50 | Best mode by KPI |
|---:|---|---:|---:|---:|---|
| 3 | none | 4 | 2,436 | 2,476 | adaptive_max (3/4) |
| 3 | ctr_drop | 4 | 2,194 | 2,190 | adaptive_max (3/4) |
| 3 | cpm_spike | 4 | 2,212 | 2,219 | adaptive_max (3/4) |
| 3 | supply_drop | 4 | 2,361 | 2,396 | adaptive_max (4/4) |
| 3 | pause | 4 | 2,416 | 2,426 | adaptive_max (4/4) |

Final dev is (fact − plan) / plan at the end of the campaign; the case threshold of 20% applies to its absolute value for spend and KPI at once (Within 20%). Trajectory error is the mean of |fact_t − plan_t| / plan_t over hours after the first 24 h. History N means the plan was built with the observable facts of N earlier campaigns on the same world seed; 0 is the public catalog alone. Live modes: adaptive_max maximises the remaining KPI every hour (primary live algorithm); adaptive keeps the approved channel mix while the projected finish is on plan and moves budget only to get back on plan or to spend what a paused channel cannot take (conservative variant).
