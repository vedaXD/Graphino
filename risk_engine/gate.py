"""HMAC-signed action gate. The executor may only act on a token issued for a
verdict that allows the exact proposal. A model cannot mint a token, and a token
for one proposal is useless for another."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

_DEV_SECRET = "dev-only-change-me"


def _secret() -> bytes:
    return os.getenv("BULWARK_GATE_SECRET", _DEV_SECRET).encode()


def _sig(payload: bytes) -> str:
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def _canon(proposal: dict) -> dict:
    return {"protocol_id": proposal["protocol_id"], "amount_usd": round(float(proposal["amount_usd"]), 2),
            "chain": proposal.get("chain")}


def issue(verdict: dict, ttl_s: int = 300, now: float | None = None) -> dict:
    """Returns {issued: bool, token?, reason?}. BLOCK never gets a token."""
    if verdict.get("outcome") not in ("ALLOW", "WARN", "ALLOW_WITH_CAP"):
        return {"issued": False, "reason": f"verdict is {verdict.get('outcome')}"}
    amt = min(float(verdict["proposal"]["amount_usd"]), float(verdict["allowed_amount_usd"]))
    body = {"proposal": _canon({**verdict["proposal"], "amount_usd": amt}),
            "exp": int((now or time.time()) + ttl_s), "rules": verdict.get("rules_version")}
    raw = json.dumps(body, sort_keys=True).encode()
    return {"issued": True, "token": base64.urlsafe_b64encode(raw).decode() + "." + _sig(raw),
            "approved_amount_usd": amt, "expires_at": body["exp"]}


def verify(token: str, proposal: dict, now: float | None = None) -> tuple[bool, str]:
    try:
        b64, sig = token.rsplit(".", 1)
        raw = base64.urlsafe_b64decode(b64.encode())
        if not hmac.compare_digest(sig, _sig(raw)):
            return False, "bad signature"
        body = json.loads(raw)
    except Exception:
        return False, "malformed token"
    if (now or time.time()) > body["exp"]:
        return False, "token expired"
    want, got = _canon(proposal), body["proposal"]
    if want["protocol_id"] != got["protocol_id"] or want["chain"] != got["chain"]:
        return False, "token is for a different proposal"
    if want["amount_usd"] > got["amount_usd"] + 0.005:
        return False, "amount exceeds the approved amount"
    return True, "ok"
