"""Constants for the MPPT Monitor integration."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "mppt_monitor"

CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "MPPT"
DEFAULT_PORT = 88
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_SCAN_INTERVAL = 10  # seconds

PROBE_TIMEOUT = 1.0          # seconds, used by the scanner
REQUEST_TIMEOUT = 10         # seconds, used by the coordinator
MIN_FIELDS = 26              # /update returns >= 26 comma-separated fields

# Charging-state logic (verified against the device firmware web UI):
#   [6]  CHS           -> 0 = charging, 1 = charge complete
#   [21] voltageInput  -> PV (solar) input voltage
#   [24] voltageOutput -> battery / output voltage
# The firmware only exposes two CHS states and keeps reporting "charging"
# when the PV voltage collapses at night, so we derive a third state.
# We also treat a low battery (output) voltage as "not charging".
PV_VOLTAGE_INDEX = 21
PV_NO_CHARGE_VOLTAGE = 5.0    # PV below this -> "not charging" (night / no sun)
BATTERY_VOLTAGE_INDEX = 24
BATTERY_NO_CHARGE_VOLTAGE = 20.0  # battery below this -> "not charging" (flat / discharging)


@dataclass(frozen=True)
class MPPTSensorDef:
    key: str
    name: str
    index: int
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    transform: str | None = None  # "float" | "charge" | "fan"


# Exactly mirrors the value_template mapping in rest/mppt.yaml & mppt-n.yaml.
SENSORS: tuple[MPPTSensorDef, ...] = (
    MPPTSensorDef("current_time", "当前时间", 0, icon="mdi:clock-outline"),
    MPPTSensorDef("run_time", "已运行时长", 1, icon="mdi:timer-outline"),
    MPPTSensorDef("charge_status", "充电状态", 6, icon="mdi:battery-charging", transform="charge"),
    MPPTSensorDef("fan_status", "风扇状态", 9, icon="mdi:fan", transform="fan"),
    MPPTSensorDef("daily_wh", "当日电量", 11, "Wh", "energy", "total", "mdi:solar-power", transform="float"),
    MPPTSensorDef("total_wh", "累计电量", 12, "Wh", "energy", "total", "mdi:solar-power-variant", transform="float"),
    MPPTSensorDef("heatsink_temp", "散热器温度", 13, "°C", "temperature", "measurement", "mdi:thermometer", transform="float"),
    MPPTSensorDef("input_power", "输入功率", 20, "W", "power", "measurement", "mdi:solar-power", transform="float"),
    MPPTSensorDef("input_voltage", "输入电压", 21, "V", "voltage", "measurement", "mdi:flash-triangle", transform="float"),
    MPPTSensorDef("input_current", "输入电流", 22, "A", "current", "measurement", "mdi:current-dc", transform="float"),
    MPPTSensorDef("output_power", "输出功率", 23, "W", "power", "measurement", "mdi:power-plug", transform="float"),
    MPPTSensorDef("output_voltage", "输出电压", 24, "V", "voltage", "measurement", "mdi:flash", transform="float"),
    MPPTSensorDef("output_current", "输出电流", 25, "A", "current", "measurement", "mdi:current-dc", transform="float"),
)
