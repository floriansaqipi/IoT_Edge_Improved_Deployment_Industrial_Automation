from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_POLICIES = {"full", "sampled_10_percent", "capped"}


@dataclass
class CloudOutputLimiter:
    policy: str
    sample_every: int = 10
    max_messages_per_second: int | None = None
    _window_second: int | None = None
    _sent_in_window: int = 0
    _seen_count: int = 0

    def __post_init__(self) -> None:
        if self.policy not in ALLOWED_POLICIES:
            raise ValueError(f"Unsupported cloud output policy: {self.policy}.")
        if self.sample_every <= 0:
            raise ValueError("sample_every must be greater than zero.")
        if self.max_messages_per_second is not None and self.max_messages_per_second <= 0:
            raise ValueError("max_messages_per_second must be greater than zero.")

    def should_forward(self, message: dict[str, Any], elapsed_seconds: float) -> bool:
        if _is_alert_or_anomaly(message):
            return True
        if self.policy == "full":
            return self._under_rate_cap(elapsed_seconds)
        if self.policy == "sampled_10_percent":
            self._seen_count += 1
            return self._seen_count % self.sample_every == 0 and self._under_rate_cap(elapsed_seconds)
        return self._under_rate_cap(elapsed_seconds)

    def _under_rate_cap(self, elapsed_seconds: float) -> bool:
        if self.max_messages_per_second is None:
            return True

        current_window = int(max(elapsed_seconds, 0.0))
        if self._window_second != current_window:
            self._window_second = current_window
            self._sent_in_window = 0

        if self._sent_in_window >= self.max_messages_per_second:
            return False
        self._sent_in_window += 1
        return True


def _is_alert_or_anomaly(message: dict[str, Any]) -> bool:
    if message.get("messageType") == "alert":
        return True
    ground_truth = message.get("groundTruth")
    return isinstance(ground_truth, dict) and bool(ground_truth.get("isAnomaly"))
