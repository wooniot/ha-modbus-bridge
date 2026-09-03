"""Config flow for Modbus Bridge."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_HOST, CONF_PORT, CONF_UNIT, DEFAULT_PORT, DEFAULT_UNIT, DOMAIN


class ModbusBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Bridge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"DS Modbus {user_input[CONF_HOST]}", data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_UNIT, default=DEFAULT_UNIT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
