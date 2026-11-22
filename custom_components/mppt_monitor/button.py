"""Button platform for the MPPT Monitor integration (restart controller)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# Mirrors /homeassistant/rest_command/mppt_restart.yaml:
#   http://admin:admin@<host>:88/Control?Type=9&Index=0&Operation=2
RESTART_PATH = "/Control?Type=9&Index=0&Operation=2"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    host: str = entry.data[CONF_HOST]
    device_name: str = entry.data.get(CONF_NAME) or host
    async_add_entities(
        [
            MPPTRestartButton(
                hass,
                host=host,
                device_name=device_name,
                username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
                password=entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            )
        ]
    )


class MPPTRestartButton(ButtonEntity):
    """Restart the MPPT controller."""

    _attr_has_entity_name = True
    _attr_translation_key = "restart"
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        device_name: str,
        username: str,
        password: str,
    ) -> None:
        self.hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._attr_unique_id = f"{host}_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=device_name,
            manufacturer="ESP32",
            model="MPPT Solar Controller",
            configuration_url=f"http://{host}:{DEFAULT_PORT}",
        )

    async def async_press(self) -> None:
        url = f"http://{self._host}:{DEFAULT_PORT}{RESTART_PATH}"
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await session.get(
                    url,
                    auth=aiohttp.BasicAuth(self._username, self._password),
                )
                await response.text()
            if response.status != 200:
                raise HomeAssistantError(
                    f"重启 {self._host} 失败: HTTP {response.status}"
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"重启 {self._host} 失败: {err}") from err
        _LOGGER.info("已向 MPPT %s 发送重启指令", self._host)
