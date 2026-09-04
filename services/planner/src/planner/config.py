import os
from dataclasses import dataclass

_ALLOWED_LOG_LEVELS = frozenset({"critical", "error", "warning", "info", "debug", "trace"})


@dataclass(frozen=True, slots=True)
class Settings:
    address: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    service_version: str = "1.0.0"

    @classmethod
    def from_env(cls) -> Settings:
        address = os.getenv("PLANNER_ADDR", "0.0.0.0").strip()
        if not address:
            raise ValueError("PLANNER_ADDR must not be empty")
        try:
            port = int(os.getenv("PLANNER_PORT", "8080"))
        except ValueError as exc:
            raise ValueError("PLANNER_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise ValueError("PLANNER_PORT must be between 1 and 65535")
        level = os.getenv("PLANNER_LOG_LEVEL", "info").lower()
        if level not in _ALLOWED_LOG_LEVELS:
            raise ValueError("invalid PLANNER_LOG_LEVEL")
        version = os.getenv("PLANNER_VERSION", "1.0.0").strip()
        if not version:
            raise ValueError("PLANNER_VERSION must not be empty")
        return cls(address=address, port=port, log_level=level, service_version=version)
