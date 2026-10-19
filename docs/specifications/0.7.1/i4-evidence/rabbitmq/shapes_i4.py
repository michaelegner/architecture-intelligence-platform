"""v0.7.1 I4 §4: two RabbitMQ shapes the I0 spike did not show, held open for a capture.

S5: one connection, two channels, both consuming queue `q.s5` with the same consumer tag `worker`.
S6: a queue named `q.s1` in vhost `/` and another `q.s1` in vhost `v2`, one consumer each.

Fake credentials, local broker, no AIP code. Usage:
  uv run --no-project --with pika==1.3.2 python shapes_i4.py <amqp_port> <seconds>
"""

import sys
import time

import pika

PORT, HOLD = int(sys.argv[1]), int(sys.argv[2])
CREDS = pika.PlainCredentials("spike", "SPIKE-FAKE-rabbit")


def connect(name: str, vhost: str = "/") -> pika.BlockingConnection:
    params = pika.ConnectionParameters(
        port=PORT,
        virtual_host=vhost,
        credentials=CREDS,
        client_properties={"connection_name": name},
    )
    return pika.BlockingConnection(params)


def noop(ch, method, props, body):
    pass


conns = []

# S5: the consumer tag is channel-scoped, so two channels of one connection may reuse it.
d = connect("svc-d")
conns.append(d)
for _ in range(2):
    ch = d.channel()
    ch.queue_declare("q.s5")
    ch.basic_consume("q.s5", noop, auto_ack=True, consumer_tag="worker")

# S6: a queue name is only unique within its vhost.
for vhost, name in (("/", "svc-e"), ("v2", "svc-f")):
    conn = connect(name, vhost)
    conns.append(conn)
    ch = conn.channel()
    ch.queue_declare("q.s1")
    ch.basic_consume("q.s1", noop, auto_ack=True, consumer_tag="s6")

end = time.time() + HOLD
while time.time() < end:
    for conn in conns:
        conn.process_data_events(time_limit=0.2)
for conn in conns:
    conn.close()
