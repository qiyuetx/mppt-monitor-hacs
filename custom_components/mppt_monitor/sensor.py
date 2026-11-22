"""Sensor platform for the MPPT Monitor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MPPTCoordinator
from .const import (
    DOMAIN,
    MPPTSensorDef,
    SENSORS,
    PV_VOLTAGE_INDEX,
    PV_NO_CHARGE_VOLTAGE,
    BATTERY_VOLTAGE_INDEX,
    BATTERY_NO_CHARGE_VOLTAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MPPTCoordinator = hass.data[DOMAIN][entry.entry_id]
    host: str = entry.data[CONF_HOST]
    device_name: str = entry.data.get(CONF_NAME) or host
    async_add_entities(
        MPPTPowerSensor(coordinator, host, device_name, definition)
        for definition in SENSORS
    )


class MPPTPowerSensor(CoordinatorEntity, SensorEntity):
    """A single field of the MPPT /update payload."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MPPTCoordinator,
        host: str,
        device_name: str,
        definition: MPPTSensorDef,
    ) -> None:
        super().__init__(coordinator)
        self._index = definition.index
        self._transform = definition.transform
        self._attr_name = definition.name
        self._attr_unique_id = f"{host}_{definition.key}"
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_class = definition.device_class
        self._attr_state_class = definition.state_class
        self._attr_icon = definition.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=device_name,
            manufacturer="ESP32",
            model="MPPT Solar Controller",
            configuration_url=f"http://{host}:88",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data or self._index >= len(data):
            return None
        raw = data[self._index]
        if self._transform == "float":
            try:
                return float(raw)
            except (ValueError, TypeError):
                return None
        if self._transform == "charge":
            # No sun at night: PV voltage collapses and firmware still says
            # "charging" (CHS=0), so treat low PV voltage as "未充电".
            if len(data) > PV_VOLTAGE_INDEX:
                try:
                    pv_voltage = float(data[PV_VOLTAGE_INDEX])
                except (ValueError, TypeError):
                    pv_voltage = None
                if pv_voltage is not None and pv_voltage < PV_NO_CHARGE_VOLTAGE:
                    return "未充电"
            # Flat / discharging battery: output (battery) voltage below the
            # threshold is also "未充电", regardless of the CHS bit.
            if len(data) > BATTERY_VOLTAGE_INDEX:
                try:
                    battery_voltage = float(data[BATTERY_VOLTAGE_INDEX])
                except (ValueError, TypeError):
                    battery_voltage = None
                if battery_voltage is not None and battery_voltage < BATTERY_NO_CHARGE_VOLTAGE:
                    return "未充电"
            try:
                state = int(float(raw))
            except (ValueError, TypeError):
                return "未知"
            return {0: "充电中", 1: "充电完成"}.get(state, "未知")
        if self._transform == "fan":
            try:
                state = int(float(raw))
            except (ValueError, TypeError):
                return "未知"
            return {0: "停止", 1: "运行"}.get(state, "未知")
        return raw
