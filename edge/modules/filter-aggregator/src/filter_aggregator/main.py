from __future__ import annotations

import os
import time

from edge_study_common.cloud_output_policy import CloudOutputLimiter
from edge_study_common.messages import OutputMessage, copy_record, utc_now
from edge_study_common.runtime import run_main


class FilterAggregator:
    def __init__(
        self,
        policy: str = "sampled_10_percent",
        sample_every: int = 10,
        max_messages_per_second: int | None = 9,
    ) -> None:
        self.policy = policy
        self.sample_every = sample_every
        self.max_messages_per_second = max_messages_per_second
        self.limiter = CloudOutputLimiter(
            policy=policy,
            sample_every=sample_every,
            max_messages_per_second=max_messages_per_second,
        )
        self.started_at = time.monotonic()

    @classmethod
    def from_env(cls) -> "FilterAggregator":
        max_mps_raw = os.getenv("CLOUD_MAX_MESSAGES_PER_SECOND", "9").strip()
        max_mps = int(max_mps_raw) if max_mps_raw else None
        return cls(
            policy=os.getenv("CLOUD_OUTPUT_POLICY", "sampled_10_percent"),
            sample_every=int(os.getenv("SAMPLE_EVERY", "10")),
            max_messages_per_second=max_mps,
        )

    def process_record(self, record: dict, elapsed_seconds: float | None = None) -> list[OutputMessage]:
        filtered = copy_record(record)
        filtered["filteredTimestamp"] = utc_now()
        elapsed = elapsed_seconds if elapsed_seconds is not None else time.monotonic() - self.started_at
        sampling_record = copy_record(filtered)
        sampling_record["groundTruth"] = {"isAnomaly": False, "anomalyType": None}
        cloud_candidate = self.limiter.should_forward(sampling_record, elapsed)
        filtered["edgeRouting"] = {
            "cloudOutputPolicy": self.policy,
            "cloudCandidate": cloud_candidate,
            "sampleEvery": self.sample_every,
            "maxMessagesPerSecond": self.max_messages_per_second,
            "routingTimestamp": utc_now(),
        }
        return [OutputMessage("filtered", filtered)]


_FILTER = FilterAggregator.from_env()


def process_record(record: dict) -> list[OutputMessage]:
    return _FILTER.process_record(record)


def main() -> int:
    return run_main("input1", process_record)


if __name__ == "__main__":
    raise SystemExit(main())
