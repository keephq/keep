"""
SNMP Provider is a class that receives SNMP traps and turns them into Keep alerts.
"""

import dataclasses
import queue
import socket
import threading
from datetime import datetime, timezone
from typing import Any

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class SnmpTrapParseError(ValueError):
    """Raised when an SNMP trap cannot be decoded."""


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP listener configuration.
    """

    listen_host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "UDP address to bind the SNMP trap listener to",
            "hint": "0.0.0.0",
        },
    )
    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port to receive SNMP traps on",
            "hint": "162",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "Accepted SNMP v1/v2c community string",
            "hint": "public",
            "sensitive": True,
        },
    )
    queue_size: int = dataclasses.field(
        default=10000,
        metadata={
            "required": False,
            "description": "Maximum decoded traps to queue before dropping new traps",
            "hint": "10000",
        },
    )
    socket_timeout_seconds: float = dataclasses.field(
        default=0.5,
        metadata={
            "required": False,
            "description": "Socket timeout used to check shutdown state",
            "hint": "0.5",
        },
    )


class _BerReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def eof(self) -> bool:
        return self.offset >= len(self.data)

    def read_tlv(self) -> tuple[int, bytes]:
        if self.offset + 2 > len(self.data):
            raise SnmpTrapParseError("Unexpected end of BER data")

        tag = self.data[self.offset]
        self.offset += 1
        length = self._read_length()
        end = self.offset + length
        if end > len(self.data):
            raise SnmpTrapParseError("BER length exceeds packet size")

        value = self.data[self.offset : end]
        self.offset = end
        return tag, value

    def _read_length(self) -> int:
        first = self.data[self.offset]
        self.offset += 1
        if first < 0x80:
            return first

        length_octets = first & 0x7F
        if length_octets == 0 or length_octets > 4:
            raise SnmpTrapParseError("Unsupported BER length form")
        if self.offset + length_octets > len(self.data):
            raise SnmpTrapParseError("Unexpected end of BER length")

        length = int.from_bytes(
            self.data[self.offset : self.offset + length_octets], "big"
        )
        self.offset += length_octets
        return length


class SnmpProvider(BaseProvider):
    """
    Receive SNMP traps and convert them into Keep alerts.

    The listener only decodes packets on the UDP thread. Pushing alerts to Keep
    happens on a worker thread so slow network I/O cannot stall packet reception.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="trap_receive",
            description="Receive SNMP v1/v2c traps on the configured UDP port.",
            mandatory=True,
            alias="Trap Receive",
        )
    ]
    FINGERPRINT_FIELDS = ["source_ip", "trap_oid", "resource"]

    SNMP_TRAP_OID_VARBIND = "1.3.6.1.6.3.1.1.4.1.0"
    V1_GENERIC_TRAPS = {
        0: ("coldStart", "1.3.6.1.6.3.1.1.5.1"),
        1: ("warmStart", "1.3.6.1.6.3.1.1.5.2"),
        2: ("linkDown", "1.3.6.1.6.3.1.1.5.3"),
        3: ("linkUp", "1.3.6.1.6.3.1.1.5.4"),
        4: ("authenticationFailure", "1.3.6.1.6.3.1.1.5.5"),
        5: ("egpNeighborLoss", "1.3.6.1.6.3.1.1.5.6"),
        6: ("enterpriseSpecific", None),
    }
    WELL_KNOWN_TRAPS = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart",
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
    }
    RESOLVED_TRAPS = {"linkUp", "warmStart"}
    CRITICAL_TRAPS = {"linkDown", "egpNeighborLoss"}
    WARNING_TRAPS = {"authenticationFailure", "enterpriseSpecific"}

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self.sock: socket.socket | None = None
        self.listener_thread: threading.Thread | None = None
        self.worker_thread: threading.Thread | None = None
        self.alert_queue: queue.Queue[dict[str, Any] | None] = queue.Queue(
            maxsize=max(1, self.authentication_config.queue_size)
        )
        self.err = ""
        self.dropped_traps = 0

    def dispose(self):
        self.stop_consume()

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **(self.config.authentication or {})
        )
        if not 0 <= self.authentication_config.listen_port <= 65535:
            raise ValueError("SNMP listen_port must be between 0 and 65535")
        if self.authentication_config.queue_size < 1:
            raise ValueError("SNMP queue_size must be greater than 0")

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(
                (
                    self.authentication_config.listen_host,
                    self.authentication_config.listen_port,
                )
            )
            sock.close()
            return {"trap_receive": True}
        except Exception as e:
            return {"trap_receive": str(e)}

    def status(self):
        return {
            "status": "running" if self.consume else "stopped",
            "error": self.err,
            "queued_traps": self.alert_queue.qsize(),
            "dropped_traps": self.dropped_traps,
        }

    def start_consume(self):
        self.consume = True
        self.worker_thread = threading.Thread(target=self._alert_worker, daemon=True)
        self.worker_thread.start()

        self.listener_thread = threading.Thread(
            target=self._listen_for_traps, daemon=True
        )
        self.listener_thread.start()

    def stop_consume(self):
        self.consume = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

        self._enqueue_sentinel()
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)

    def _listen_for_traps(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(self.authentication_config.socket_timeout_seconds)
            self.sock.bind(
                (
                    self.authentication_config.listen_host,
                    self.authentication_config.listen_port,
                )
            )
        except Exception as e:
            self.err = str(e)
            self.logger.exception("Failed to start SNMP trap listener")
            self.consume = False
            self._enqueue_sentinel()
            return

        self.logger.info(
            "SNMP trap listener started",
            extra={
                "listen_host": self.authentication_config.listen_host,
                "listen_port": self.authentication_config.listen_port,
            },
        )

        while self.consume:
            try:
                packet, address = self.sock.recvfrom(65535)
                decoded = self._parse_snmp_message(packet)
                if decoded.get("community") != self.authentication_config.community:
                    self.logger.warning(
                        "Discarding SNMP trap with unexpected community"
                    )
                    continue
                decoded["source_ip"] = address[0]
                alert = self._alert_from_decoded(decoded)
                self._enqueue_alert(alert.dict())
            except socket.timeout:
                continue
            except OSError:
                if self.consume:
                    self.logger.exception("SNMP socket error")
                break
            except Exception:
                self.logger.exception("Failed to decode SNMP trap")

        self._enqueue_sentinel()

    def _enqueue_alert(self, alert: dict[str, Any]):
        try:
            self.alert_queue.put_nowait(alert)
        except queue.Full:
            self.dropped_traps += 1
            self.logger.warning("SNMP alert queue is full, dropping trap")

    def _enqueue_sentinel(self):
        try:
            self.alert_queue.put_nowait(None)
        except queue.Full:
            pass

    def _alert_worker(self):
        while self.consume or not self.alert_queue.empty():
            try:
                alert = self.alert_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if alert is None:
                self.alert_queue.task_done()
                break

            try:
                self._push_alert(alert)
            except Exception:
                self.logger.exception("Failed to push SNMP alert")
            finally:
                self.alert_queue.task_done()

    @classmethod
    def _alert_from_datagram(cls, packet: bytes, source_ip: str) -> AlertDto:
        decoded = cls._parse_snmp_message(packet)
        decoded["source_ip"] = source_ip
        return cls._alert_from_decoded(decoded)

    @classmethod
    def _parse_snmp_message(cls, packet: bytes) -> dict[str, Any]:
        reader = _BerReader(packet)
        tag, message = reader.read_tlv()
        if tag != 0x30 or not reader.eof():
            raise SnmpTrapParseError("SNMP message must be a single BER sequence")

        message_reader = _BerReader(message)
        version = cls._expect_integer(message_reader, "SNMP version")
        community = cls._expect_octet_string(message_reader, "community")
        pdu_tag, pdu = message_reader.read_tlv()

        if pdu_tag == 0xA4:
            return cls._parse_v1_trap(version, community, pdu)
        if pdu_tag in (0xA6, 0xA7):
            return cls._parse_v2_trap(version, community, pdu, pdu_tag)
        raise SnmpTrapParseError(f"Unsupported SNMP PDU tag 0x{pdu_tag:02x}")

    @classmethod
    def _parse_v1_trap(cls, version: int, community: str, pdu: bytes) -> dict[str, Any]:
        reader = _BerReader(pdu)
        enterprise_oid = cls._expect_oid(reader, "enterprise")
        agent_address = cls._decode_value(*reader.read_tlv())
        generic_trap = cls._expect_integer(reader, "generic trap")
        specific_trap = cls._expect_integer(reader, "specific trap")
        uptime = cls._decode_value(*reader.read_tlv())
        varbinds = cls._parse_varbinds(reader.read_tlv())

        trap_name, trap_oid = cls.V1_GENERIC_TRAPS.get(
            generic_trap, ("enterpriseSpecific", None)
        )
        if trap_oid is None:
            trap_oid = f"{enterprise_oid}.0.{specific_trap}"

        return {
            "version": "v1" if version == 0 else f"version-{version}",
            "community": community,
            "trap_name": trap_name,
            "trap_oid": trap_oid,
            "enterprise_oid": enterprise_oid,
            "agent_address": agent_address,
            "generic_trap": generic_trap,
            "specific_trap": specific_trap,
            "uptime": uptime,
            "varbinds": varbinds,
        }

    @classmethod
    def _parse_v2_trap(
        cls, version: int, community: str, pdu: bytes, pdu_tag: int
    ) -> dict[str, Any]:
        reader = _BerReader(pdu)
        request_id = cls._expect_integer(reader, "request id")
        error_status = cls._expect_integer(reader, "error status")
        error_index = cls._expect_integer(reader, "error index")
        varbinds = cls._parse_varbinds(reader.read_tlv())

        trap_oid = next(
            (
                varbind["value"]
                for varbind in varbinds
                if varbind["oid"] == cls.SNMP_TRAP_OID_VARBIND
            ),
            None,
        )
        trap_name = cls.WELL_KNOWN_TRAPS.get(trap_oid, "enterpriseSpecific")

        return {
            "version": "v2c" if version == 1 else f"version-{version}",
            "community": community,
            "pdu_type": "trap" if pdu_tag == 0xA7 else "inform",
            "request_id": request_id,
            "error_status": error_status,
            "error_index": error_index,
            "trap_name": trap_name,
            "trap_oid": trap_oid or "unknown",
            "varbinds": varbinds,
        }

    @classmethod
    def _parse_varbinds(cls, tlv: tuple[int, bytes]) -> list[dict[str, Any]]:
        tag, value = tlv
        if tag != 0x30:
            raise SnmpTrapParseError("SNMP varbind list must be a sequence")

        varbinds = []
        reader = _BerReader(value)
        while not reader.eof():
            varbind_tag, varbind_value = reader.read_tlv()
            if varbind_tag != 0x30:
                raise SnmpTrapParseError("SNMP varbind must be a sequence")

            varbind_reader = _BerReader(varbind_value)
            oid = cls._expect_oid(varbind_reader, "varbind oid")
            value_tag, raw_value = varbind_reader.read_tlv()
            varbinds.append(
                {
                    "oid": oid,
                    "value": cls._decode_value(value_tag, raw_value),
                    "type": cls._value_type(value_tag),
                }
            )
        return varbinds

    @classmethod
    def _alert_from_decoded(cls, trap: dict[str, Any]) -> AlertDto:
        trap_name = trap.get("trap_name") or cls.WELL_KNOWN_TRAPS.get(
            trap.get("trap_oid"), "enterpriseSpecific"
        )
        trap_oid = trap.get("trap_oid") or "unknown"
        source_ip = trap.get("source_ip") or trap.get("agent_address") or "unknown"
        resource = cls._resource_from_varbinds(trap.get("varbinds", []))
        status = cls._status_for_trap(trap_name)
        severity = cls._severity_for_trap(trap_name, trap.get("varbinds", []))
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        labels = cls._labels_from_trap(trap, source_ip, resource)

        return AlertDto(
            id=f"snmp:{source_ip}:{trap_oid}:{resource}",
            name=f"SNMP {trap_name} from {source_ip}",
            status=status,
            severity=severity,
            lastReceived=timestamp,
            firingStartTime=timestamp,
            source=["snmp"],
            message=f"SNMP {trap.get('version', 'trap')} {trap_name} received from {source_ip}",
            description=cls._description_from_trap(trap),
            fingerprint=f"snmp:{source_ip}:{trap_oid}:{resource}",
            labels=labels,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        return SnmpProvider._alert_from_decoded(
            {
                "version": event.get("version", "webhook"),
                "source_ip": event.get("source_ip")
                or event.get("agent_address")
                or event.get("host")
                or event.get("hostname"),
                "trap_name": event.get("trap_name") or event.get("name"),
                "trap_oid": event.get("trap_oid") or event.get("oid"),
                "varbinds": event.get("varbinds", []),
            }
        )

    @staticmethod
    def _expect_integer(reader: _BerReader, field_name: str) -> int:
        tag, value = reader.read_tlv()
        if tag != 0x02:
            raise SnmpTrapParseError(f"Expected integer for {field_name}")
        return int.from_bytes(value, "big", signed=bool(value and value[0] & 0x80))

    @staticmethod
    def _expect_octet_string(reader: _BerReader, field_name: str) -> str:
        tag, value = reader.read_tlv()
        if tag != 0x04:
            raise SnmpTrapParseError(f"Expected octet string for {field_name}")
        return value.decode("utf-8", errors="replace")

    @classmethod
    def _expect_oid(cls, reader: _BerReader, field_name: str) -> str:
        tag, value = reader.read_tlv()
        if tag != 0x06:
            raise SnmpTrapParseError(f"Expected OID for {field_name}")
        return cls._decode_oid(value)

    @classmethod
    def _decode_value(cls, tag: int, value: bytes) -> Any:
        if tag == 0x02:
            return int.from_bytes(value, "big", signed=bool(value and value[0] & 0x80))
        if tag == 0x04:
            return value.decode("utf-8", errors="replace")
        if tag == 0x05:
            return None
        if tag == 0x06:
            return cls._decode_oid(value)
        if tag == 0x40:
            return ".".join(str(part) for part in value)
        if tag in (0x41, 0x42, 0x43, 0x46, 0x47):
            return int.from_bytes(value, "big")
        return value.hex()

    @staticmethod
    def _value_type(tag: int) -> str:
        return {
            0x02: "integer",
            0x04: "octet_string",
            0x05: "null",
            0x06: "object_identifier",
            0x40: "ip_address",
            0x41: "counter32",
            0x42: "gauge32",
            0x43: "time_ticks",
            0x46: "counter64",
            0x47: "uinteger32",
        }.get(tag, f"tag_0x{tag:02x}")

    @staticmethod
    def _decode_oid(value: bytes) -> str:
        if not value:
            raise SnmpTrapParseError("OID value is empty")

        first = value[0]
        if first < 40:
            oid = [0, first]
        elif first < 80:
            oid = [1, first - 40]
        else:
            oid = [2, first - 80]
        current = 0
        for byte in value[1:]:
            current = (current << 7) | (byte & 0x7F)
            if not byte & 0x80:
                oid.append(current)
                current = 0
        if current:
            raise SnmpTrapParseError("OID base128 value did not terminate")
        return ".".join(str(part) for part in oid)

    @staticmethod
    def _resource_from_varbinds(varbinds: list[dict[str, Any]]) -> str:
        for varbind in varbinds:
            if varbind.get("oid") in {
                "1.3.6.1.2.1.2.2.1.2",
                "1.3.6.1.2.1.31.1.1.1.1",
            }:
                return str(varbind.get("value"))
        for varbind in varbinds:
            if varbind.get("oid") != SnmpProvider.SNMP_TRAP_OID_VARBIND:
                return str(varbind.get("value"))
        return "device"

    @classmethod
    def _status_for_trap(cls, trap_name: str) -> AlertStatus:
        return (
            AlertStatus.RESOLVED
            if trap_name in cls.RESOLVED_TRAPS
            else AlertStatus.FIRING
        )

    @classmethod
    def _severity_for_trap(
        cls, trap_name: str, varbinds: list[dict[str, Any]]
    ) -> AlertSeverity:
        if trap_name in cls.CRITICAL_TRAPS:
            return AlertSeverity.CRITICAL
        if trap_name in cls.WARNING_TRAPS:
            return AlertSeverity.WARNING
        if trap_name in cls.RESOLVED_TRAPS:
            return AlertSeverity.INFO

        text = " ".join(str(varbind.get("value", "")).lower() for varbind in varbinds)
        if any(term in text for term in ("critical", "fatal", "down")):
            return AlertSeverity.CRITICAL
        if any(term in text for term in ("warning", "warn", "degraded")):
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    @staticmethod
    def _labels_from_trap(
        trap: dict[str, Any], source_ip: str, resource: str
    ) -> dict[str, str]:
        labels = {
            "source_ip": source_ip,
            "trap_name": str(trap.get("trap_name", "enterpriseSpecific")),
            "trap_oid": str(trap.get("trap_oid", "unknown")),
            "snmp_version": str(trap.get("version", "unknown")),
            "resource": resource,
        }
        for varbind in trap.get("varbinds", []):
            labels[f"oid_{varbind.get('oid')}"] = str(varbind.get("value"))
        return labels

    @staticmethod
    def _description_from_trap(trap: dict[str, Any]) -> str:
        varbinds = trap.get("varbinds", [])
        if not varbinds:
            return "SNMP trap received without varbinds"
        values = ", ".join(
            f"{varbind.get('oid')}={varbind.get('value')}" for varbind in varbinds
        )
        return f"SNMP trap varbinds: {values}"
