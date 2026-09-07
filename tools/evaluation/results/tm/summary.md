# Experiment B: traffic-manager quality (paired with frozen execution)


## Live modes by shock (conversions, 1.2M, 21 d, history 3)

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive · none | 16 | +0.6% | +0.2% | 100% | — | — | — | 6% | 100.0% | 8.9% |
| adaptive · ctr_drop | 16 | +5.0% | +0.2% | 94% | +52% | 24 | 81% | 28% | 100.0% | 5.1% |
| adaptive · cpm_spike | 16 | +4.0% | +0.1% | 94% | +50% | 8 | 75% | 26% | 100.0% | 3.9% |
| adaptive · supply_drop | 16 | +0.9% | +0.1% | 94% | +102% | 104 | 62% | 20% | 100.0% | 8.8% |
| adaptive · pause | 16 | +6.6% | +5.1% | 100% | +114% | 7 | 100% | 33% | 100.0% | 7.6% |
| adaptive_max · none | 16 | +2.7% | +0.3% | 88% | — | — | — | 32% | 100.0% | 8.1% |
| adaptive_max · ctr_drop | 16 | +6.4% | +2.7% | 100% | +68% | 7 | 100% | 43% | 100.0% | 5.7% |
| adaptive_max · cpm_spike | 16 | +5.3% | +2.2% | 100% | +72% | 6 | 100% | 46% | 100.0% | 5.8% |
| adaptive_max · supply_drop | 16 | +2.4% | +0.2% | 94% | +269% | 80 | 88% | 31% | 100.0% | 8.6% |
| adaptive_max · pause | 16 | +8.1% | +5.8% | 100% | +136% | 7 | 100% | 42% | 100.0% | 7.0% |
| adaptive · all shocks | 80 | +3.2% | +0.2% | 96% | +97% | 8 | 80% | 25% | 100.0% | 7.2% |
| adaptive_max · all shocks | 80 | +4.0% | +0.9% | 96% | +111% | 7 | 97% | 38% | 100.0% | 7.4% |

## Live modes by shock (conversions, 1.2M, 21 d, history 0)

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive · none | 16 | +0.5% | -0.1% | 75% | — | — | — | 6% | 100.0% | 13.2% |
| adaptive · ctr_drop | 16 | +4.8% | -0.1% | 81% | +54% | 4 | 50% | 11% | 100.0% | 10.5% |
| adaptive · cpm_spike | 16 | +4.0% | -0.1% | 75% | +55% | 6 | 50% | 20% | 100.0% | 11.4% |
| adaptive · supply_drop | 16 | +1.4% | +0.0% | 88% | +143% | 16 | 50% | 8% | 100.0% | 12.7% |
| adaptive · pause | 16 | +11.0% | +4.4% | 94% | +272% | 7 | 100% | 37% | 100.0% | 14.3% |
| adaptive_max · none | 16 | +24.1% | +15.1% | 100% | — | — | — | 110% | 100.0% | 33.4% |
| adaptive_max · ctr_drop | 16 | +30.6% | +21.1% | 100% | +450% | 4 | 100% | 122% | 100.0% | 29.3% |
| adaptive_max · cpm_spike | 16 | +28.8% | +19.4% | 100% | +516% | 4 | 100% | 121% | 100.0% | 28.2% |
| adaptive_max · supply_drop | 16 | +24.5% | +16.6% | 100% | +1990% | 14 | 100% | 115% | 100.0% | 29.9% |
| adaptive_max · pause | 16 | +29.5% | +21.1% | 100% | +671% | 6 | 94% | 119% | 100.0% | 31.8% |
| adaptive · all shocks | 80 | +6.4% | -0.1% | 82% | +174% | 7 | 62% | 30% | 100.0% | 12.7% |
| adaptive_max · all shocks | 80 | +28.2% | +16.7% | 100% | +672% | 6 | 98% | 118% | 100.0% | 31.0% |

## Noisy world: random market events on, no scripted shock

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive · history 3 | 16 | +0.7% | +0.0% | 75% | — | — | — | 3% | 100.0% | 7.6% |
| adaptive_max · history 3 | 16 | +2.8% | +0.2% | 88% | — | — | — | 33% | 100.0% | 7.6% |
| adaptive_max · history 0 | 16 | +25.6% | +14.7% | 100% | — | — | — | 115% | 100.0% | 30.5% |

## Ablations of the live loop (adaptive_max, history 3)

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hourly, with recent facts · none | 16 | +2.7% | +0.3% | 88% | — | — | — | 32% | 100.0% | 8.1% |
| hourly, with recent facts · ctr_drop | 16 | +6.4% | +2.7% | 100% | +68% | 7 | 100% | 43% | 100.0% | 5.7% |
| hourly, no recent facts · none | 16 | -0.2% | -1.8% | 44% | — | — | — | 29% | 100.0% | 7.7% |
| hourly, no recent facts · ctr_drop | 16 | +3.4% | +0.6% | 94% | +34% | 116 | 100% | 37% | 100.0% | 6.4% |
| every 6 h · none | 16 | +2.4% | +0.5% | 94% | — | — | — | 32% | 100.0% | 8.9% |
| every 6 h · ctr_drop | 16 | +5.8% | +2.3% | 100% | +60% | 9 | 100% | 41% | 100.0% | 5.6% |
| every 24 h · none | 16 | +1.3% | -0.3% | 88% | — | — | — | 25% | 100.0% | 9.4% |
| every 24 h · ctr_drop | 16 | +4.4% | +2.4% | 100% | +57% | 16 | 100% | 37% | 100.0% | 6.1% |

## Shock timing (CTR −40 % on the top channel, adaptive_max, history 3)

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hour 120 (day 6) | 16 | +8.3% | +2.7% | 100% | +43% | 8 | 100% | 46% | 100.0% | 9.5% |
| hour 252 (day 11) | 16 | +6.4% | +2.7% | 100% | +68% | 7 | 100% | 43% | 100.0% | 5.7% |
| hour 400 (day 17) | 16 | +3.6% | +1.4% | 94% | +122% | 6 | 100% | 37% | 100.0% | 9.0% |

## KPI = clicks (history 3)

| Slice | Pairs | Uplift p50 | Uplift p10 | Wins | Recovered p50 | Reaction h p50 | Reacted | Reallocated p50 | Budget use p50 | |Dev KPI| p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive_max · none | 16 | +1.1% | +0.4% | 100% | — | — | — | 28% | 100.0% | 7.8% |
| adaptive_max · ctr_drop | 16 | +6.8% | +3.9% | 100% | +54% | 6 | 100% | 58% | 100.0% | 5.8% |

## Baselines: hand rebalancing once a day versus frozen, and adaptive_max versus hand

| History | Shock | Pairs | Manual over frozen p50 | Manual wins | adaptive_max over manual p50 | adaptive_max over manual p10 | adaptive_max wins over manual |
|---:|---|---:|---:|---:|---:|---:|---:|
| 3 | none | 16 | +0.1% | 50% | +2.2% | -0.0% | 88% |
| 3 | ctr_drop | 16 | +1.1% | 81% | +4.7% | +1.7% | 100% |
| 3 | cpm_spike | 16 | +0.6% | 75% | +4.1% | +2.0% | 94% |
| 3 | supply_drop | 16 | -0.1% | 44% | +1.5% | +0.5% | 94% |
| 3 | pause | 16 | +0.0% | 50% | +8.9% | +5.3% | 100% |
| 3 | all | 80 | +0.3% | 60% | +3.8% | +0.7% | 95% |
| 0 | none | 16 | +16.5% | 100% | +3.6% | +1.7% | 94% |
| 0 | ctr_drop | 16 | +19.1% | 100% | +6.3% | +1.9% | 94% |
| 0 | cpm_spike | 16 | +18.1% | 100% | +5.5% | +1.2% | 94% |
| 0 | supply_drop | 16 | +16.2% | 88% | +4.6% | +1.3% | 94% |
| 0 | pause | 16 | +16.7% | 100% | +9.2% | +3.3% | 94% |
| 0 | all | 80 | +17.3% | 98% | +5.9% | +1.6% | 94% |

Manual is a hand rule without a model: once a day, move 20 % of the remaining budget from channels with a worse than average cost per KPI yesterday toward the better ones, at most 30 % per channel per day, hourly shapes as approved.

Uplift is the live mode's fact KPI over frozen execution of the same approved plan on the same world, seed and shock; wins is the share of pairs with positive uplift. Recovered is the share of the KPI the shock took from frozen execution that the live mode won back: (live − frozen_shock) / (frozen_calm − frozen_shock). Reaction is the number of hours after the shock until the live plan cut the shocked channel's cap by 20 % relative to the same live mode without the shock (6 h smoothing); reacted is the share of shocked pairs where that happened at all. Reallocated is the share of budget moved away from the approved caps. |Dev KPI| is the case metric of the live run: its final deviation from the approved plan.
