"""Config flow for the MPPT Monitor integration."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MIN_FIELDS,
    PROBE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def _guess_network() -> str:
    """Return the known MPPT network as the scan default."""
    return "10.0.30.0/24"


async def _probe_with_session(
    session: aiohttp.ClientSession, host: str, username: str, password: str
) -> bool:
    url = f"http://{host}:88/update"
    try:
        async with asyncio.timeout(PROBE_TIMEOUT):
            response = await session.get(
                url, auth=aiohttp.BasicAuth(username, password)
            )
            text = await response.text()
        if response.status != 200:
            return False
        return len(text.strip().split(",")) >= MIN_FIELDS
    except (aiohttp.ClientError, TimeoutError, OSError):
        return False


class MPPTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding an MPPT controller via UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}
        self._scan_username = DEFAULT_USERNAME
        self._scan_password = DEFAULT_PASSWORD

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user", menu_options=["manual", "scan"]
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
            password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            if not await _probe_with_session(session, host, username, password):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or host,
                    data={
                        CONF_HOST: host,
                        CONF_NAME: user_input.get(CONF_NAME) or host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
            }
        )
        return self.async_show_form(
            step_id="manual", data_schema=schema, errors=errors
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            network_text = str(user_input.get("network", "")).strip() or _guess_network()
            username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
            password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            try:
                network = ipaddress.ip_network(network_text, strict=False)
            except ValueError:
                errors["network"] = "invalid_network"
            else:
                self._scan_username = username
                self._scan_password = password
                self._discovered = await self._scan_network(
                    network, username, password
                )
                if not self._discovered:
                    errors["base"] = "no_devices_found"
                else:
                    return await self.async_step_select()

        schema = vol.Schema(
            {
                vol.Optional("network", default=_guess_network()): str,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="scan", data_schema=schema, errors=errors
        )

    async def _scan_network(
        self, network: ipaddress.IPv4Network | ipaddress.IPv6Network,
        username: str, password: str,
    ) -> dict[str, str]:
        session = async_get_clientsession(self.hass)
        hosts = [str(host) for host in network.hosts()]
        semaphore = asyncio.Semaphore(48)

        async def check(host: str) -> str | None:
            async with semaphore:
                ok = await _probe_with_session(session, host, username, password)
                return host if ok else None

        results = await asyncio.gather(*(check(host) for host in hosts))
        found = [host for host in results if host]
        found.sort(key=lambda ip: ipaddress.ip_address(ip))
        return {host: f"{host} — MPPT 控制器" for host in found}

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or host,
                data={
                    CONF_HOST: host,
                    CONF_NAME: user_input.get(CONF_NAME) or host,
                    CONF_USERNAME: self._scan_username,
                    CONF_PASSWORD: self._scan_password,
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): vol.In(self._discovered),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
            }
        )
        return self.async_show_form(
            step_id="select", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MPPTOptionsFlow()


class MPPTOptionsFlow(OptionsFlow):
    """Let the user change the polling interval without editing code."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
