#!/bin/sh
# usage: run-svc.sh <short-name> <port>   (short-name: catalog-service|product-query-service|image-service)

n=$1; p=$2
docker rm -f s111-$n >/dev/null 2>&1
docker run -d --name s111-$n --network host -v $S/sokol111/ecommerce-$n:/src:ro -v $S/sokol-bin/$n:/app/svc:ro -v /tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/874c3fe3-3fde-42b6-b9aa-fef20038bfc3/scratchpad/live/cfg:/cfg:ro -w /tmp/w \
 -e CONFIG_FILE=/cfg/$n.yaml -e MULTI_TENANCY__ENABLED=false -e APP_SERVICE_NAME=ecommerce-$n -e APP_ENV=standalone -e APP_SERVICE_VERSION=frozen \
 -e SERVER__PORT=$p -e MONGO__CONNECTION_STRING='mongodb://localhost:27017/?replicaSet=rs0&directConnection=true' \
 -e MONGO__HOST=localhost -e KAFKA__BROKERS=localhost:9092 \
 -e SECURITY__JWKS__ENABLED=false -e SECURITY__TOKEN__ENABLED=false \
 -e OBSERVABILITY__OTEL_COLLECTOR_ENDPOINT=localhost:4317 -e OBSERVABILITY__TRACING__SAMPLE_RATIO=1 \
 golang:1.26 sh -c "mkdir -p /tmp/w && cp -r /src/configs /src/db /tmp/w/ 2>/dev/null; exec /app/svc"
