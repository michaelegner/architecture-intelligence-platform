# RabbitMQ contrast spike — commands

Fake credentials only (`spike` / `SPIKE-FAKE-rabbit`), local loopback, 2026-10-16. Throwaway container, removed afterwards.

```bash
# image: rabbitmq:3-management-alpine (RabbitMQ 3.13.7)
docker run -d --name aip-i01-rmq -p 127.0.0.1:15673:15672 -p 127.0.0.1:5673:5672 \
  -e RABBITMQ_DEFAULT_USER=spike -e RABBITMQ_DEFAULT_PASS=SPIKE-FAKE-rabbit \
  rabbitmq@sha256:606d8c0d6b3c18d1da9afc53bc7cdb2a8d5486df91b5a9830e9e07626c9ae281

# declare shapes S1-S4 and hold consumers open for 40 s
uv run --no-project --with pika==1.3.2 python shapes.py 5673 40

# while they are held (each file in raw/ has a .meta with timestamp, command, exit code)
curl -s -u spike:SPIKE-FAKE-rabbit localhost:15673/api/{consumers,queues,bindings,connections,channels,overview}
docker rm -f aip-i01-rmq
```

| Shape | Setup |
|---|---|
| S1 | queue `q.s1`, two consumers (`s1-c1`, `s1-c2`), two channels of connection `svc-a` |
| S2 | fanout exchange `x.s2`, queues `q.s2a`/`q.s2b`, one consumer each from connections `svc-b` and `svc-c` |
| S3 | every connection sets the client property `connection_name` (`svc-a/b/c`) |
| S4 | queue `q.s4` bound to direct exchange `x.s4`, no consumer |
