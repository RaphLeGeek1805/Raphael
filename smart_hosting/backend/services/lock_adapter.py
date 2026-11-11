"""
Lock Adapter — abstract interface toward smart lock manufacturer APIs.
Currently implemented as a stub that logs commands.
Nuki-compatible interface; extend for Yale, igloohome, etc.
"""
import logging
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)


class LockAdapterBase:
    """Abstract base for lock provider adapters."""

    def set_code(self, external_lock_id: str, code: str,
                 valid_from: datetime, valid_until: datetime) -> dict:
        raise NotImplementedError

    def revoke_code(self, external_lock_id: str, code: str) -> dict:
        raise NotImplementedError

    def get_status(self, external_lock_id: str) -> dict:
        raise NotImplementedError


class StubAdapter(LockAdapterBase):
    """
    Stub adapter — simulates all lock operations and logs commands.
    Use this during development or when no real API key is configured.
    """

    def set_code(self, external_lock_id: str, code: str,
                 valid_from: datetime, valid_until: datetime) -> dict:
        logger.info(
            f"[LOCK STUB] SET CODE | lock={external_lock_id} code=REDACTED "
            f"from={valid_from.isoformat()} until={valid_until.isoformat()}"
        )
        return {
            "status": "ok",
            "provider": "stub",
            "lock_id": external_lock_id,
            "action": "set_code",
            "simulated": True,
        }

    def revoke_code(self, external_lock_id: str, code: str) -> dict:
        logger.info(
            f"[LOCK STUB] REVOKE CODE | lock={external_lock_id} code=REDACTED"
        )
        return {
            "status": "ok",
            "provider": "stub",
            "lock_id": external_lock_id,
            "action": "revoke_code",
            "simulated": True,
        }

    def get_status(self, external_lock_id: str) -> dict:
        import random
        battery = random.randint(60, 100)
        status = "online" if battery > 10 else "low_battery"
        logger.info(
            f"[LOCK STUB] GET STATUS | lock={external_lock_id} → status={status} battery={battery}%"
        )
        return {
            "status": status,
            "battery_level": battery,
            "provider": "stub",
            "lock_id": external_lock_id,
            "simulated": True,
        }


class NukiAdapter(LockAdapterBase):
    """
    Nuki Bridge API adapter (v3).
    Requires NUKI_BRIDGE_HOST and NUKI_BRIDGE_TOKEN in config.
    Falls back to StubAdapter if not configured.
    """

    def __init__(self, bridge_host: str, token: str):
        self.bridge_host = bridge_host
        self.token = token
        self._stub = StubAdapter()

    def set_code(self, external_lock_id: str, code: str,
                 valid_from: datetime, valid_until: datetime) -> dict:
        if not self.bridge_host or not self.token:
            logger.warning("[NUKI] No credentials — falling back to stub")
            return self._stub.set_code(external_lock_id, code, valid_from, valid_until)

        # Real Nuki Bridge API call would go here
        # POST http://<bridge>/lockAction?nukiId=<id>&token=<token>&action=1
        logger.info(f"[NUKI] SET CODE on lock {external_lock_id}")
        return {"status": "ok", "provider": "nuki", "lock_id": external_lock_id}

    def revoke_code(self, external_lock_id: str, code: str) -> dict:
        if not self.bridge_host or not self.token:
            return self._stub.revoke_code(external_lock_id, code)
        logger.info(f"[NUKI] REVOKE CODE on lock {external_lock_id}")
        return {"status": "ok", "provider": "nuki", "lock_id": external_lock_id}

    def get_status(self, external_lock_id: str) -> dict:
        if not self.bridge_host or not self.token:
            return self._stub.get_status(external_lock_id)
        logger.info(f"[NUKI] GET STATUS for lock {external_lock_id}")
        return {"status": "online", "battery_level": 80, "provider": "nuki", "lock_id": external_lock_id}


def get_adapter(provider: str) -> LockAdapterBase:
    """
    Factory: return the right adapter for the given provider name.
    Falls back to StubAdapter if provider is unknown or unconfigured.
    """
    if provider == "nuki":
        try:
            bridge_host = current_app.config.get("NUKI_BRIDGE_HOST", "")
            token = current_app.config.get("NUKI_BRIDGE_TOKEN", "")
            return NukiAdapter(bridge_host, token)
        except RuntimeError:
            # Outside app context
            return StubAdapter()

    # yale, igloohome, other → stub for now
    return StubAdapter()
