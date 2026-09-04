from planner.domain.models import Allocation, Horizon


def allocate_uniformly(
    budget_micros: int, horizon: Horizon, channels: list[str]
) -> tuple[Allocation, ...]:
    if budget_micros < 0:
        raise ValueError("budget must not be negative")
    ordered_channels = sorted(channels)
    slots = (horizon.to_hour - horizon.from_hour) * len(ordered_channels)
    if slots <= 0:
        raise ValueError("allocation requires a positive horizon and at least one channel")
    quotient, remainder = divmod(budget_micros, slots)
    result: list[Allocation] = []
    index = 0
    for hour in range(horizon.from_hour, horizon.to_hour):
        for channel_id in ordered_channels:
            result.append(Allocation(channel_id, hour, quotient + (1 if index < remainder else 0)))
            index += 1
    return tuple(result)
