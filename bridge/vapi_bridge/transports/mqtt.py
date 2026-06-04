"""
MQTT Transport — Listens for PoAC records on MQTT broker.

Topic scheme:
  vapi/poac/{device_id_hex}  — 228-byte binary PoAC record payload
  vapi/status/{device_id_hex} — JSON status heartbeat (optional)

Compatible with the Pebble's NB-IoT → MQTT bridge (e.g., AWS IoT Core,
HiveMQ, Mosquitto).
"""

import asyncio
import logging
import re

import aiomqtt

from ..codec import PoACRecord, parse_record, POAC_RECORD_SIZE
from ..config import Config

log = logging.getLogger(__name__)

# Topic must match {prefix}/{vapi-subtopic}/{64-hex-device-id}. Anything else
# (control chars, broker wildcards, embedded slashes, attacker-shaped payloads)
# is rejected before it can flow into the `source` string used downstream.
_TOPIC_SUFFIX_RE = re.compile(r"^(poac|status)/[0-9a-fA-F]{1,64}$")
_TOPIC_MAX_LEN = 256


def _is_valid_topic(topic: str, prefix: str) -> bool:
    if not isinstance(topic, str) or not topic or len(topic) > _TOPIC_MAX_LEN:
        return False
    # No control chars, no NUL, no MQTT broker wildcards in the consumed string.
    if any(c in topic for c in ("\x00", "\r", "\n", "+", "#")):
        return False
    if not topic.startswith(prefix + "/"):
        return False
    suffix = topic[len(prefix) + 1:]
    return bool(_TOPIC_SUFFIX_RE.match(suffix))


class MqttTransport:
    """Async MQTT listener for PoAC records."""

    def __init__(self, cfg: Config, on_record):
        """
        Args:
            cfg: Bridge configuration.
            on_record: Async callback(raw_data: bytes, source: str) for each record.
        """
        self._cfg = cfg
        self._on_record = on_record

    async def run(self):
        """Connect to MQTT broker and listen for records."""
        topic = f"{self._cfg.mqtt_topic_prefix}/#"
        log.info(
            "MQTT connecting to %s:%d (topic=%s)",
            self._cfg.mqtt_broker, self._cfg.mqtt_port, topic,
        )

        _fail_count = 0
        _backoff = 5  # seconds, doubles on each failure up to _BACKOFF_CAP
        _BACKOFF_CAP = 300  # 5 minutes max between retries

        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self._cfg.mqtt_broker,
                    port=self._cfg.mqtt_port,
                    username=self._cfg.mqtt_username or None,
                    password=self._cfg.mqtt_password or None,
                ) as client:
                    await client.subscribe(topic)
                    log.info("MQTT subscribed to %s", topic)
                    _fail_count = 0
                    _backoff = 5  # reset on successful connect

                    async for message in client.messages:
                        await self._handle_message(message)

            except aiomqtt.MqttError as e:
                _fail_count += 1
                if _fail_count == 1:
                    log.warning(
                        "MQTT connection failed: %s — retrying with backoff "
                        "(subsequent failures suppressed to DEBUG)",
                        e,
                    )
                else:
                    log.debug(
                        "MQTT connection lost (attempt %d): %s — retrying in %ds",
                        _fail_count, e, _backoff,
                    )
                await asyncio.sleep(_backoff)
                _backoff = min(_backoff * 2, _BACKOFF_CAP)
            except asyncio.CancelledError:
                log.info("MQTT transport shutting down")
                raise

    async def _handle_message(self, message):
        """Process a single MQTT message."""
        payload = message.payload
        topic = str(message.topic)

        if not _is_valid_topic(topic, self._cfg.mqtt_topic_prefix):
            log.warning("MQTT: rejecting message on malformed topic (len=%d)",
                        len(topic))
            return

        if len(payload) == POAC_RECORD_SIZE:
            source = f"mqtt:{topic}"
            try:
                await self._on_record(bytes(payload), source)
            except Exception as e:
                log.error("Error processing MQTT record: %s", e)
        elif len(payload) > 0:
            log.debug(
                "MQTT: ignoring %d-byte message on %s (expected %d)",
                len(payload), topic, POAC_RECORD_SIZE,
            )
