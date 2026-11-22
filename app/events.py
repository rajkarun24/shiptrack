"""Kafka producer: the API uses this to publish events instead of doing the work itself."""
import uuid

from confluent_kafka import KafkaException, Producer

from app.models import Status, StatusEvent


class EventPublishError(Exception):
    pass


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._topic = topic
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",                 # wait until the broker confirms it saved the message
            "enable.idempotence": True,    # a retry can't create a duplicate message
            "message.timeout.ms": 5000,    # give up after 5s so the API can answer with an error
        })

    def publish_status(self, parcel_id: str, status: Status) -> StatusEvent:
        event = StatusEvent(event_id=uuid.uuid4().hex, parcel_id=parcel_id, status=status)
        errors: list = []

        def on_delivery(err, _msg):
            if err is not None:
                errors.append(err)

        try:
            # key = parcel_id: all events for one parcel go to the same partition, so they
            # stay in order.
            self._producer.produce(self._topic, key=parcel_id,
                                   value=event.model_dump_json(), on_delivery=on_delivery)
            remaining = self._producer.flush(6)
        except KafkaException as exc:
            raise EventPublishError(str(exc)) from exc
        if errors or remaining > 0:
            raise EventPublishError(str(errors[0]) if errors else "broker did not confirm")
        return event

    def ping(self) -> bool:
        try:
            self._producer.list_topics(timeout=2)
            return True
        except KafkaException:
            return False
