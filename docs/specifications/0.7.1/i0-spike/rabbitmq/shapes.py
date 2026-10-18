"""Declare the I0.1 RabbitMQ shapes S1-S4 and hold their consumers open.

Spike only: fake credentials, local broker, no AIP code. Usage:
  uv run --no-project --with pika==1.3.2 python shapes.py <amqp_port> <seconds>
"""

import sys
import time

import pika

PORT, HOLD = int(sys.argv[1]), int(sys.argv[2])
CREDS = pika.PlainCredentials("spike", "SPIKE-FAKE-rabbit")


def connect(name: str) -> pika.BlockingConnection:
    params = pika.ConnectionParameters(
        port=PORT,
        credentials=CREDS,
        client_properties={"connection_name": name},
    )
    return pika.BlockingConnection(params)


def noop(ch, method, props, body):  # pragma: no cover - spike
    pass


conns = []

# S1: one queue, two competing consumers from one connection (two channels).
a = connect("svc-a")
conns.append(a)
for tag in ("s1-c1", "s1-c2"):
    ch = a.channel()
    ch.queue_declare("q.s1")
    ch.basic_consume("q.s1", noop, auto_ack=True, consumer_tag=tag)

# S2: fanout exchange, two bound queues, one consumer each from two connections.
b, c = connect("svc-b"), connect("svc-c")
conns += [b, c]
chb = b.channel()
chb.exchange_declare("x.s2", "fanout")
for conn, q, tag in ((b, "q.s2a", "s2-b"), (c, "q.s2b", "s2-c")):
    ch = conn.channel()
    ch.queue_declare(q)
    ch.queue_bind(q, "x.s2")
    ch.basic_consume(q, noop, auto_ack=True, consumer_tag=tag)

# S4: bound queue with no consumer.
ch4 = a.channel()
ch4.exchange_declare("x.s4", "direct")
ch4.queue_declare("q.s4")
ch4.queue_bind("q.s4", "x.s4", routing_key="k")

end = time.time() + HOLD
while time.time() < end:
    for conn in conns:
        conn.process_data_events(time_limit=0.2)
for conn in conns:
    conn.close()
