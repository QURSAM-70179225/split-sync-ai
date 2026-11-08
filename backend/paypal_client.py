"""Minimal PayPal REST (Sandbox) client: OAuth2 + Orders v2."""
from __future__ import annotations

import time
import uuid

import requests

from config import get_settings


class PayPalError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502, details: object | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


_token_cache: dict[str, float | str] = {"token": "", "expires_at": 0.0}


def _base() -> str:
    return get_settings().paypal_base_url.rstrip("/")


def is_configured() -> bool:
    s = get_settings()
    return bool(s.paypal_client_id and s.paypal_client_secret)


def get_access_token() -> str:
    """Client-credentials grant against /v1/oauth2/token (cached until expiry)."""
    if _token_cache["token"] and time.time() < float(_token_cache["expires_at"]) - 60:
        return str(_token_cache["token"])
    s = get_settings()
    if not is_configured():
        raise PayPalError("PayPal credentials are not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET).", 503)
    resp = requests.post(
        f"{_base()}/v1/oauth2/token",
        auth=(s.paypal_client_id, s.paypal_client_secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if resp.status_code != 200:
        raise PayPalError("PayPal authentication failed — check your sandbox credentials.", 502, _safe_json(resp))
    body = resp.json()
    _token_cache["token"] = body["access_token"]
    _token_cache["expires_at"] = time.time() + int(body.get("expires_in", 300))
    return body["access_token"]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": str(uuid.uuid4()),
    }


def _safe_json(resp: requests.Response) -> object:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def create_paypal_order(
    amount: float,
    currency: str,
    description: str,
    *,
    reference_id: str | None = None,
    payee_email: str | None = None,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> dict:
    """Create a CAPTURE order. Returns {'order_id', 'approval_url', 'status'}."""
    s = get_settings()
    purchase_unit: dict = {
        "amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"},
        "description": description[:127],
    }
    if reference_id:
        purchase_unit["reference_id"] = reference_id[:256]
    if payee_email:
        purchase_unit["payee"] = {"email_address": payee_email}

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [purchase_unit],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "brand_name": "SplitSync AI",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "return_url": return_url or f"{s.frontend_url}/?paypal=success",
                    "cancel_url": cancel_url or f"{s.frontend_url}/?paypal=cancel",
                }
            }
        },
    }
    resp = requests.post(f"{_base()}/v2/checkout/orders", json=payload, headers=_headers(), timeout=30)
    if resp.status_code not in (200, 201):
        raise PayPalError("PayPal order creation failed.", 502, _safe_json(resp))
    body = resp.json()
    approval = next(
        (link["href"] for link in body.get("links", []) if link.get("rel") in ("payer-action", "approve")), None
    )
    if not approval:
        raise PayPalError("PayPal did not return an approval link.", 502, body)
    return {"order_id": body["id"], "approval_url": approval, "status": body.get("status")}


def capture_paypal_order(order_id: str) -> dict:
    resp = requests.post(
        f"{_base()}/v2/checkout/orders/{order_id}/capture", headers=_headers(), timeout=30
    )
    body = _safe_json(resp)
    if resp.status_code not in (200, 201):
        # Already captured is fine (e.g. page refresh)
        if isinstance(body, dict) and any(
            d.get("issue") == "ORDER_ALREADY_CAPTURED" for d in body.get("details", [])
        ):
            return {"status": "COMPLETED", "already_captured": True}
        raise PayPalError("PayPal capture failed.", 502, body)
    return body
