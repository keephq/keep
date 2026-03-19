"""
Pure SNMP varBinds -> Keep alert formatting utilities.

These utilities are intentionally dependency-light so unit tests can run without
importing the full provider/runtime (DB connections, context manager, etc.).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from keep.api.models.alert import AlertSeverity, AlertStatus

# SNMPv2-MIB::snmpTrapOID.0 (value is the trap's enterprise / notification OID)
SNMP_TRAP_OID_NUMERIC = "1.3.6.1.6.3.1.1.4.1.0"


def format_trap_alert(varBinds) -> dict:
    """
    Convert pysnmp Notification varBinds into a Keep alert dict.

    This is used by the SNMP provider but kept separate for testability.
    """

    lines: list[str] = []
    trap_oid: str | None = None

    for oid, val in varBinds:
        o = oid.prettyPrint()
        v = val.prettyPrint() if val is not None else ""
        lines.append(f"{o} = {v}")

        # Different PySNMP versions / OID encodings may expose snmpTrapOID.0 in different ways.
        if (
            o == SNMP_TRAP_OID_NUMERIC
            or SNMP_TRAP_OID_NUMERIC in o
            or o.endswith("snmpTrapOID.0")
        ):
            trap_oid = v

    body = "\n".join(lines)
    if not trap_oid and lines:
        # Fallback: first varbind key is sometimes the most informative.
        trap_oid = lines[0].split("=", 1)[0].strip()

    name = trap_oid or "snmp-trap"
    if "." in name:
        short = name.split(".")[-1]
        if short and short[0].isdigit():
            name = f"snmp-trap-{short}"
        else:
            name = short or name

    fp_src = f"{trap_oid}|{body}"
    fingerprint = hashlib.sha256(fp_src.encode("utf-8", errors="replace")).hexdigest()[
        :32
    ]
    now = datetime.now(tz=timezone.utc).isoformat()

    return {
        "id": str(uuid.uuid4()),
        "name": name[:500],
        "status": AlertStatus.FIRING,
        "severity": AlertSeverity.WARNING,
        "lastReceived": now,
        "environment": "snmp",
        "service": "snmp",
        "source": ["snmp"],
        "message": body[:4000] if body else "SNMP trap (no varbinds)",
        "description": body[:16000] if body else "SNMP trap (no varbinds)",
        "fingerprint": fingerprint,
        "labels": {"trap_oid": trap_oid or ""},
    }

