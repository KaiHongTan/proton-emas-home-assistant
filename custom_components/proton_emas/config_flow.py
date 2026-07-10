"""Config flow for Proton e.MAS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EMASApi, EMASApiError, EMASAuthError
from .const import (
    CONF_API_BASE,
    CONF_APP_VERSION,
    CONF_APP_VERSION_CODE,
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    CONF_TITLE,
    CONF_TOKEN,
    CONF_VIN,
    DEFAULT_API_BASE,
    DEFAULT_APP_VERSION,
    DEFAULT_APP_VERSION_CODE,
    DEFAULT_CLIENT_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TENANT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VIN): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_TITLE): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=30, max=3600)
        ),
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


class ProtonEMASConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ProtonEMASOptionsFlow()

    async def _async_validate_token(self, vin: str, token: str) -> dict[str, str]:
        """Validate credentials against the cloud API."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        api = EMASApi(session, vin=vin, token=token)
        try:
            await api.get_vehicle_status()
        except EMASAuthError:
            errors["base"] = "invalid_auth"
        except EMASApiError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating credentials")
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            token = user_input[CONF_TOKEN].strip()
            title = (user_input.get(CONF_TITLE) or "").strip() or f"Proton e.MAS {vin[-6:]}"
            scan = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_token(vin, token)

            if not errors:
                options = {
                    CONF_SCAN_INTERVAL: scan,
                    CONF_API_BASE: DEFAULT_API_BASE,
                    CONF_TENANT_ID: DEFAULT_TENANT_ID,
                    CONF_CLIENT_ID: DEFAULT_CLIENT_ID,
                    CONF_APP_VERSION: DEFAULT_APP_VERSION,
                    CONF_APP_VERSION_CODE: DEFAULT_APP_VERSION_CODE,
                }
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_VIN: vin,
                        CONF_TOKEN: token,
                        CONF_TITLE: title,
                    },
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            errors = await self._async_validate_token(entry.data[CONF_VIN], token)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user replace an expired Bearer token on an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            errors = await self._async_validate_token(entry.data[CONF_VIN], token)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"vin": entry.data[CONF_VIN]},
        )


class ProtonEMASOptionsFlow(OptionsFlow):
    """Advanced options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            new_opts = {**self.config_entry.options}
            for key, val in user_input.items():
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    continue
                if isinstance(val, str):
                    val = val.strip()
                new_opts[key] = val
            return self.async_create_entry(title="", data=new_opts)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                vol.Optional(
                    CONF_API_BASE,
                    description={
                        "suggested_value": opts.get(CONF_API_BASE, DEFAULT_API_BASE)
                    },
                ): str,
                vol.Optional(
                    CONF_TENANT_ID,
                    description={
                        "suggested_value": opts.get(CONF_TENANT_ID, DEFAULT_TENANT_ID)
                    },
                ): str,
                vol.Optional(
                    CONF_CLIENT_ID,
                    description={
                        "suggested_value": opts.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID)
                    },
                ): str,
                vol.Optional(
                    CONF_APP_VERSION,
                    description={
                        "suggested_value": opts.get(CONF_APP_VERSION, DEFAULT_APP_VERSION)
                    },
                ): str,
                vol.Optional(
                    CONF_APP_VERSION_CODE,
                    description={
                        "suggested_value": opts.get(
                            CONF_APP_VERSION_CODE, DEFAULT_APP_VERSION_CODE
                        )
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
