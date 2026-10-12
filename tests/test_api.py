"""Tests for the HTTP client helpers."""

from __future__ import annotations

import base64
import json
import time

import pytest

from custom_components.proton_emas.api import (
    EMASApiError,
    EMASAuthError,
    _unwrap,
    token_expiry,
)

from .conftest import make_jwt


def test_token_expiry_reads_login_time_plus_timeout() -> None:
    exp = int(time.time()) + 3600
    assert int(token_expiry(make_jwt(exp)).timestamp()) == exp


def test_token_expiry_prefers_standard_exp() -> None:
    def enc(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    token = f"{enc({'alg': 'HS256'})}.{enc({'exp': 2000000000, 'loginTime': 1, 'timeout': 1})}.sig"
    assert int(token_expiry(token).timestamp()) == 2000000000


@pytest.mark.parametrize("token", ["", "opaque-token", "a.b.c", "a.!!!.c"])
def test_token_expiry_non_jwt_is_none(token: str) -> None:
    assert token_expiry(token) is None


def test_unwrap_envelope() -> None:
    assert _unwrap({"code": 200, "data": {"x": 1}}) == {"x": 1}
    with pytest.raises(EMASAuthError):
        _unwrap({"code": 401, "msg": "expired"})
    with pytest.raises(EMASApiError, match="code 424"):
        _unwrap({"code": 424, "msg": "kicked"})
