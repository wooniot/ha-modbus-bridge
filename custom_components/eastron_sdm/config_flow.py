"""Config flow for the Eastron SDM Energy Meters integration.

One config entry = one gateway/RS485 connection. Meters are added as
"meter" config subentries under that entry - either in a loop right
after configuring the connection (this file's main ConfigFlow), or
later, one at a time, via the "+ Add device" button on the
integration's entry (MeterSubentryFlowHandler below).
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_MODEL,
    CONF_PARITY,
    CONF_SCAN_INTERVAL,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    CONF_WAIT_BETWEEN_REQUESTS,
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STOPBITS,
    DEFAULT_TCP_PORT,
    DEFAULT_WAIT_BETWEEN_REQUESTS_NETWORK,
    DEFAULT_WAIT_BETWEEN_REQUESTS_SERIAL,
    DOMAIN,
    MODEL_SDM630,
    MODELS,
    PARITY_OPTIONS,
    SUBENTRY_TYPE_METER,
)
from .modbus_client import gateway_key

# Option labels for both selectors below live in strings.json/translations
# (under "selector") via translation_key, not as literal strings here, so
# they follow the user's Home Assistant language instead of always
# showing up in whatever language they were first written in.
CONNECTION_TYPE_OPTIONS = [CONNECTION_RTU_OVER_TCP, CONNECTION_TCP, CONNECTION_SERIAL]


def _model_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=MODELS,
            mode=SelectSelectorMode.LIST,
            translation_key="model",
        )
    )


def _unit_id_selector() -> NumberSelector:
    # Box mode (a text field with +/- steppers) rather than a slider:
    # a slider makes it fiddly to land on a precise address, especially
    # on a phone, so it should look and behave just like the polling
    # interval field below.
    return NumberSelector(
        NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
    )


def _scan_interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=1, max=3600, step=1, mode=NumberSelectorMode.BOX)
    )


def _meter_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", "Eastron meter")): str,
            vol.Required(
                CONF_MODEL, default=defaults.get(CONF_MODEL, MODEL_SDM630)
            ): _model_selector(),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, 1)
            ): _unit_id_selector(),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): _scan_interval_selector(),
        }
    )


def _duplicate_unit_id(
    unit_id: int, others: list[dict[str, Any]]
) -> bool:
    return any(m.get(CONF_UNIT_ID) == unit_id for m in others)


class EastronSdmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one gateway, then add one or more meters on it in a
    loop before creating the entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._gateway_data: dict[str, Any] = {}
        self._meters: list[dict[str, Any]] = []

    # -- gateway connection ------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._gateway_data[CONF_CONNECTION_TYPE] = user_input[CONF_CONNECTION_TYPE]
            if user_input[CONF_CONNECTION_TYPE] == CONNECTION_SERIAL:
                return await self.async_step_serial()
            return await self.async_step_network()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECTION_TYPE, default=CONNECTION_RTU_OVER_TCP
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=CONNECTION_TYPE_OPTIONS,
                        mode=SelectSelectorMode.LIST,
                        translation_key=CONF_CONNECTION_TYPE,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        is_reconfigure = self.source == config_entries.SOURCE_RECONFIGURE

        if user_input is not None:
            self._gateway_data["host"] = user_input["host"]
            self._gateway_data["tcp_port"] = user_input["tcp_port"]
            self._gateway_data[CONF_WAIT_BETWEEN_REQUESTS] = user_input[
                CONF_WAIT_BETWEEN_REQUESTS
            ]
            if is_reconfigure:
                return self._async_finish_reconfigure()
            return await self.async_step_meter()

        # A "transparent" RTU-over-TCP bridge is really a serial bus
        # underneath, so it tends to need the same slack a direct
        # serial connection would; a native Modbus TCP gateway usually
        # queues requests itself and can get away with less.
        default_wait = self._gateway_data.get(
            CONF_WAIT_BETWEEN_REQUESTS,
            DEFAULT_WAIT_BETWEEN_REQUESTS_SERIAL
            if self._gateway_data.get(CONF_CONNECTION_TYPE) == CONNECTION_RTU_OVER_TCP
            else DEFAULT_WAIT_BETWEEN_REQUESTS_NETWORK,
        )
        schema = vol.Schema(
            {
                vol.Required("host", default=self._gateway_data.get("host", "")): str,
                vol.Required(
                    "tcp_port", default=self._gateway_data.get("tcp_port", DEFAULT_TCP_PORT)
                ): int,
                vol.Required(
                    CONF_WAIT_BETWEEN_REQUESTS, default=default_wait
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000)),
            }
        )
        return self.async_show_form(step_id="network", data_schema=schema)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        is_reconfigure = self.source == config_entries.SOURCE_RECONFIGURE

        if user_input is not None:
            self._gateway_data["port"] = user_input["port"]
            self._gateway_data[CONF_BAUDRATE] = user_input[CONF_BAUDRATE]
            self._gateway_data[CONF_PARITY] = user_input[CONF_PARITY]
            self._gateway_data[CONF_STOPBITS] = user_input[CONF_STOPBITS]
            self._gateway_data[CONF_BYTESIZE] = user_input[CONF_BYTESIZE]
            self._gateway_data[CONF_WAIT_BETWEEN_REQUESTS] = user_input[
                CONF_WAIT_BETWEEN_REQUESTS
            ]
            if is_reconfigure:
                return self._async_finish_reconfigure()
            return await self.async_step_meter()

        schema = vol.Schema(
            {
                vol.Required(
                    "port", default=self._gateway_data.get("port", "/dev/ttyUSB0")
                ): str,
                vol.Required(
                    CONF_BAUDRATE, default=self._gateway_data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
                ): vol.In([2400, 4800, 9600, 19200, 38400]),
                vol.Required(
                    CONF_PARITY, default=self._gateway_data.get(CONF_PARITY, DEFAULT_PARITY)
                ): vol.In(PARITY_OPTIONS),
                vol.Required(
                    CONF_STOPBITS, default=self._gateway_data.get(CONF_STOPBITS, DEFAULT_STOPBITS)
                ): vol.In([1, 2]),
                vol.Required(
                    CONF_BYTESIZE, default=self._gateway_data.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
                ): vol.In([7, 8]),
                vol.Required(
                    CONF_WAIT_BETWEEN_REQUESTS,
                    default=self._gateway_data.get(
                        CONF_WAIT_BETWEEN_REQUESTS, DEFAULT_WAIT_BETWEEN_REQUESTS_SERIAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000)),
            }
        )
        return self.async_show_form(step_id="serial", data_schema=schema)

    # -- reconfigure (gateway connection only, meters untouched) ------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user tweak the gateway's connection settings (host,
        serial params, wait_between_requests, ...) without touching the
        meters already configured under this entry. The connection
        type itself (TCP/RTU-over-TCP/serial) can't be changed here -
        that's a different enough setup that remove-and-re-add is
        clearer than trying to migrate it in place."""
        entry = self._get_reconfigure_entry()
        self._gateway_data = dict(entry.data)
        if self._gateway_data[CONF_CONNECTION_TYPE] == CONNECTION_SERIAL:
            return await self.async_step_serial()
        return await self.async_step_network()

    @callback
    def _async_finish_reconfigure(self) -> config_entries.ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        new_unique_id = "|".join(str(part) for part in gateway_key(self._gateway_data))
        return self.async_update_reload_and_abort(
            entry, unique_id=new_unique_id, data=self._gateway_data
        )

    # -- meters, added in a loop --------------------------------------------

    async def async_step_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if _duplicate_unit_id(user_input[CONF_UNIT_ID], self._meters):
                errors["unit_id"] = "duplicate_unit_id"
            else:
                self._meters.append(
                    {
                        "name": user_input["name"],
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    }
                )
                return await self.async_step_add_another()

        next_unit_id = max((m[CONF_UNIT_ID] for m in self._meters), default=0) + 1
        defaults = {"name": f"Eastron meter {next_unit_id}", CONF_UNIT_ID: next_unit_id}
        return self.async_show_form(
            step_id="meter", data_schema=_meter_schema(defaults), errors=errors
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="add_another",
            menu_options=["meter", "finish"],
            description_placeholders={"count": str(len(self._meters))},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        unique_id = "|".join(str(part) for part in gateway_key(self._gateway_data))
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        label = self._gateway_data.get("host") or self._gateway_data.get("port") or "gateway"
        title = f"Eastron gateway ({label})"

        subentries = [
            {
                "subentry_type": SUBENTRY_TYPE_METER,
                "data": meter,
                "title": meter["name"],
                "unique_id": str(meter[CONF_UNIT_ID]),
            }
            for meter in self._meters
        ]
        return self.async_create_entry(
            title=title, data=self._gateway_data, subentries=subentries
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_METER: MeterSubentryFlowHandler}


class MeterSubentryFlowHandler(ConfigSubentryFlow):
    """Add ("+ Add device") or reconfigure a single meter subentry,
    without having to touch the gateway connection again."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_form(user_input, is_new=True)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_form(user_input, is_new=False)

    async def _async_step_form(
        self, user_input: dict[str, Any] | None, is_new: bool
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        existing = None if is_new else self._get_reconfigure_subentry()
        parent_entry = self._get_entry()

        other_meters = [
            sub.data
            for sub in parent_entry.subentries.values()
            if sub.subentry_type == SUBENTRY_TYPE_METER
            and (existing is None or sub.subentry_id != existing.subentry_id)
        ]

        if user_input is not None:
            if _duplicate_unit_id(user_input[CONF_UNIT_ID], other_meters):
                errors["unit_id"] = "duplicate_unit_id"
            else:
                data = {
                    "name": user_input["name"],
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                }
                if is_new:
                    return self.async_create_entry(
                        title=data["name"], data=data, unique_id=str(data[CONF_UNIT_ID])
                    )
                return self.async_update_and_abort(
                    parent_entry, existing, title=data["name"], data=data
                )

        defaults = existing.data if existing else {}
        step_id = "user" if is_new else "reconfigure"
        return self.async_show_form(
            step_id=step_id, data_schema=_meter_schema(defaults), errors=errors
        )
