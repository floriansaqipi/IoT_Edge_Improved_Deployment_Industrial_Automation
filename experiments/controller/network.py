from __future__ import annotations

from dataclasses import dataclass


CLOUD_PORTS = "443,5671,8883"
DEFAULT_REMOTE_SCRIPT = "/home/floriansaqipi/iot_edge_study/ubuntu-network-emulation.sh"


@dataclass(frozen=True)
class NetworkCommandPlan:
    condition: str
    show_command: str
    apply_command: str | None
    clear_command: str
    outage_start_second: int | None = None
    outage_duration_second: int | None = None
    recovery_duration_second: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition,
            "showCommand": self.show_command,
            "applyCommand": self.apply_command,
            "clearCommand": self.clear_command,
            "outageStartSecond": self.outage_start_second,
            "outageDurationSecond": self.outage_duration_second,
            "recoveryDurationSecond": self.recovery_duration_second,
        }


def build_network_plan(
    condition: str,
    iot_hub_host: str,
    duration_seconds: float,
    script_path: str = DEFAULT_REMOTE_SCRIPT,
) -> NetworkCommandPlan:
    base = f"sudo {script_path} --host {iot_hub_host} --ports {CLOUD_PORTS}"
    show = f"{base} show"
    clear = f"{base} clear"
    if condition == "normal":
        return NetworkCommandPlan(condition=condition, show_command=show, apply_command=None, clear_command=clear)
    if condition == "delay_200ms":
        return NetworkCommandPlan(
            condition=condition,
            show_command=show,
            apply_command=f"{base} apply --condition delay_200ms",
            clear_command=clear,
        )
    if condition == "cloud_outage_120s":
        start, outage, recovery = outage_schedule_seconds(duration_seconds)
        return NetworkCommandPlan(
            condition=condition,
            show_command=show,
            apply_command=f"{base} apply --condition cloud_outage_block",
            clear_command=clear,
            outage_start_second=start,
            outage_duration_second=outage,
            recovery_duration_second=recovery,
        )
    if condition.startswith("packet_loss_"):
        return NetworkCommandPlan(
            condition=condition,
            show_command=show,
            apply_command=f"{base} apply --condition {condition}",
            clear_command=clear,
        )
    raise ValueError(f"Unsupported network condition: {condition}")


def outage_schedule_seconds(duration_seconds: float) -> tuple[int, int, int]:
    if int(duration_seconds) == 300:
        return 90, 120, 90
    pre = max(1, round(duration_seconds * 0.3))
    outage = max(1, round(duration_seconds * 0.4))
    recovery = max(1, int(duration_seconds) - pre - outage)
    return pre, outage, recovery
