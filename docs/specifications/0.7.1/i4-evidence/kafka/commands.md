# Commands and environment

**Host:** Linux 5.15 (WSL2), Docker 29.8.2. **Date:** 2026-10-19 (UTC). Pinned clone outside the AIP checkout; `git status` was empty before and after.

## Environment (no repository file changed)

- `env.txt`: `DB_USER=postgres`, `DB_PASSWORD=postgres`, `REDIS_PASSWORD=`, `ENV=development` (from `.env.example`).
- `override.yml`:
  - pins `kafka` to `confluentinc/cp-kafka:7.5.0@sha256:fbbb6fa1…bf41`;
  - mounts a throwaway RSA keypair (`openssl genrsa 2048`, outside the clone) over payment-service's `/app/keys`. It is not committed.
- `KAFKA_CONSUMER_GROUP` is unset, so payment-service uses its default group `payment-service`.

```bash
docker compose -p aip-i41 --env-file env.txt -f docker-compose.yml -f override.yml \
  up -d --build postgres redis zookeeper kafka payment-service order-service
```

## Recorded steps

Each step is recorded in `raw/NN-*.txt` (unchanged stdout), `raw/NN-*.meta` (UTC, exact command, exit code, and the environment where it matters) and `raw/NN-*.err` (non-empty stderr only). Broker commands ran in `ecommerce-kafka` with `--bootstrap-server kafka:29092`.

`.txt` and `.err` files are verbatim. Three kinds of edit were made to `.meta` files after recording:

- an `env:` line was appended to 12, 12a and 28;
- the local evidence-directory prefix was shortened in the `--out` paths of 12, 12a and 28;
- the local clone path in 17 became `<ecommerce-system checkout>`.

Timestamps, commands and exit codes are unchanged.

| Files | Step |
|---|---|
| 00a, 00b | start stock `kafka-console-consumer` groups `ops-tail` (`orders.created`) and `analytics-tap` (`payments.completed`) |
| 01–07 | **G1**: `--list`, `--describe --group G --members --verbose` for all four groups, `--describe --all-groups --state`, `--describe --all-groups` |
| 08–11 | `kafka-topics --describe`, `kafka-topics --version`, image digest, container images |
| — | commit `expected.json` (C1) + `EXPECTED.sha256` |
| 12a | capture with the README command as written: failed, `ModuleNotFoundError: app` |
| 12 | **C1**: `KAFKA_BOOTSTRAP_SERVERS=localhost:9092 PYTHONPATH=. uv run --with confluent-kafka==2.16.0 python harness/kafka-capture/capture.py --broker-id kafka:ecommerce-local --environment local --group order-service --group payment-service --group ops-tail --out c1/kafka-consumer-state.json` |
| 13–16 | **G1'**: members describe again, identical to G1 |
| 17 | `gen_kafka_payloads.py 6 \| kafka-console-producer --topic orders.created` (real traffic) |
| 18 | offsets while attached: `payment-service` and `ops-tail` at offset 6 on partition 1 |
| 19, 20 | stop `ops-tail` (`pkill -TERM`) and `docker stop ecommerce-payment-service` |
| 21–27 | **G2**: list, members, state and offsets. Both stopped groups are `Empty` with committed offsets |
| — | commit the `expected.json` C2 part + digest |
| 28 | **C2**: same capture command, `--out c2/kafka-consumer-state.json` |
| 29 | **G2'**: state again, identical to G2 |

Teardown: `docker compose -p aip-i41 … down -v`. No `ecommerce-*` containers remain, and the clone is clean.
