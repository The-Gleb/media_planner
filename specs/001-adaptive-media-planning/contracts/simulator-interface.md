# Simulator domain interface

This is the in-process boundary implemented by the simulation engine. The HTTP adapter in
`openapi.yaml` supplies resource identity, conditional concurrency and idempotent retry around it.

```go
type Simulator interface {
    Reset(cfg SimulationConfig) error
    Step(actions []ChannelAction) ([]Observation, error)
    CurrentHour() Hour
}

type SimulationConfig struct {
    WorldSeed     int64
    CampaignSeed  int64
    StartHour     Hour
    DurationHours int
    TimeZone      string
}

type ChannelAction struct {
    ChannelID ChannelID

    // Compatibility boundary only. Step validates finite/non-negative input and
    // converts it exactly once to MoneyMicros before any calculation.
    BudgetCap float64
}

type Observation struct {
    ChannelID   ChannelID
    Hour        Hour
    Requests    int64
    Impressions int64
    UniqueReach int64
    Clicks      int64
    Conversions int64
    Spend       MoneyMicros
    ECPM        *DecimalMoney
}
```

## Semantics

- `Reset` is atomic. On success `CurrentHour()` equals StartHour and cumulative state is zero.
- The first successful `Step` observes StartHour, commits all channels, then advances CurrentHour by
  exactly 60 minutes.
- Actions may omit configured channels; omission means a zero budget cap. Unknown or duplicate IDs
  are errors.
- Results contain every configured active channel in stable ChannelID order.
- An error MUST NOT modify current hour, cumulative state or deterministic replay position.
- After DurationHours successful steps, further calls return `ErrSimulationFinished`.
- `CurrentHour` is the next hour not yet simulated. Before a successful Reset it returns the zero Hour;
  the HTTP resource does not exist in this state.
- One `Simulator` instance is not called concurrently by the adapter; resource locking is an adapter
  responsibility.

## Money compatibility note

The HTTP contract is normative for service-to-service communication and uses decimal strings.
`float64 BudgetCap` is retained only because it was requested as the Go façade. It MUST NOT be stored,
multiplied or accumulated. Values with more than six meaningful decimals are rounded half away from
zero once at the boundary and the quantized value is used for all subsequent logic and output.
