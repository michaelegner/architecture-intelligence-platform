# Commands and environment

**System:** `hungCS22hcmiu/ecommerce-system` at `cd65365838ea880185a02e6536fa347439bfa274` (checkout clean: `git status` empty before and after).  
**Host:** Linux 5.15.153.1-microsoft-standard-WSL2, Docker 29.8.1, Docker Compose v5.5.1. **Run date:** 2026-10-13 (UTC).

## Environment assumptions (no repository file was changed)

- `env.txt` (outside the checkout): `DB_USER=postgres`, `DB_PASSWORD=postgres`, `REDIS_PASSWORD=`, `ENV=development`
  (values from the repository's `.env.example`).
- `payment-service` mounts `./user-service/keys` (JWT public key, gitignored, absent from the checkout). A
  throwaway RSA keypair was generated outside the checkout (`openssl genrsa 2048`) and bound over `/app/keys`
  through a compose override file. The keys are not committed.
- Slice started: `postgres`, `redis`, `zookeeper`, `kafka`, `payment-service`, `order-service`. Not started:
  user, cart, product, ai, frontend, nginx.
- The Kafka broker/zookeeper/Postgres/Redis images are the repository's own pins
  (`confluentinc/cp-kafka:7.5.0`, `confluentinc/cp-zookeeper:7.5.0`, `pgvector/pgvector:pg15`, `redis:7-alpine`); image ids are in `raw/16-image-ids.txt`.
  `payment-service` and `order-service` were built from the checkout's Dockerfiles.
- No traffic was generated: group/member state is what the check targets. No application or instrumentation change.

## Run

```bash
docker compose -p hungcs-r6 --env-file env.txt -f docker-compose.yml -f override.yml \
  up -d --build postgres redis zookeeper kafka payment-service order-service
# wait until `kafka-consumer-groups --list` shows both groups (≈1 min after the services start)
```

Captures (`raw/NN-*.txt` = unchanged stdout, `raw/NN-*.meta` = UTC timestamp, exact command, exit code,
`raw/NN-*.err` only if stderr was non-empty). Kafka commands run inside the `ecommerce-kafka` container with
`--bootstrap-server kafka:29092`:

| File | Command |
|---|---|
| 01 | `kafka-consumer-groups --list` |
| 02, 03 | `kafka-consumer-groups --describe --group payment-service` / `order-service` |
| 04, 05 | `… --describe --group G --members --verbose` |
| 06, 07 | `… --describe --group G --state` |
| 08, 09 | `kafka-topics --list` / `--describe` |
| 10 | `docker compose -p hungcs-r6 ps --format json` |
| 11–13 | `docker inspect` network addresses of payment, order and kafka containers |
| 14 | `docker images --digests …` **failed** (invalid invocation: `docker images` takes one argument). Kept unchanged as a record; image ids come from file 16 instead |
| 15 | `docker inspect` container id and hostname of payment and order |
| 16 | `docker inspect` image ids |

Teardown: `docker compose -p hungcs-r6 … down -v`; afterwards no `ecommerce-*` containers remain and the checkout is still clean.
