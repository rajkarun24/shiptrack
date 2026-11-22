"""Worker service: reads status events from Kafka and updates the database.

Run with:  python -m app.worker
Same Docker image as the API, different start command.
"""
import logging
import signal
import sys

from confluent_kafka import Consumer, KafkaError
from pydantic import ValidationError

from app.cache import RedisCache
from app.config import get_worker_settings
from app.models import StatusEvent
from app.store import PostgresStore

logger = logging.getLogger("shiptrack.worker")


def handle_message(raw: bytes, store, cache) -> str:
    """Process ONE message. Returns 'updated' or 'skipped'.
    Raises on real failures (e.g. database down), so the message is retried."""
    try:
        event = StatusEvent.model_validate_json(raw)
    except ValidationError:
        logger.error("skipping malformed message: %r", raw[:200])
        return "skipped"          # retrying a broken message would never help

    parcel = store.update_status(event.parcel_id, event.status)
    if parcel is None:
        logger.warning("skipping event %s: parcel %s not found", event.event_id, event.parcel_id)
        return "skipped"
    cache.delete(event.parcel_id)  # cached copy is now stale
    logger.info("parcel %s -> %s (event %s)", event.parcel_id, event.status.value, event.event_id)
    return "updated"


def main() -> None:
    s = get_worker_settings()
    logging.basicConfig(level=s.log_level)
    store = PostgresStore(s.database_url)
    cache = RedisCache(s.redis_url, ttl_seconds=60)

    consumer = Consumer({
        "bootstrap.servers": s.kafka_bootstrap_servers,
        "group.id": s.kafka_group_id,
        "auto.offset.reset": "earliest",   # a brand-new group starts from the beginning
        "enable.auto.commit": False,       # we commit ourselves, AFTER the work succeeded
    })
    consumer.subscribe([s.kafka_topic])

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)   # docker stop sends SIGTERM
    signal.signal(signal.SIGINT, stop)

    logger.info("worker started, listening on topic %s", s.kafka_topic)
    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("kafka error: %s", msg.error())
                continue
            handle_message(msg.value(), store, cache)
            consumer.commit(message=msg, asynchronous=False)   # "done, don't send it again"
    except Exception:
        # Crash on purpose. Docker restarts us, and since we never committed this message,
        # Kafka delivers it again. That is "at-least-once" processing.
        logger.exception("worker failed, exiting so it gets restarted")
        sys.exit(1)
    finally:
        consumer.close()
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
