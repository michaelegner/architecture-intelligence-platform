# Evidence — REST Provider/Caller and gRPC Boundary

All permalinks are rooted at:

```text
https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/
```

## Caller-side evidence (rest-fights)

[`rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/HeroRestClient.java`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/HeroRestClient.java):

```java
@Path("/api/heroes")
@RegisterRestClient(configKey = "hero-client")
interface HeroRestClient {
	@GET
	@Path("/random")
	Uni<Hero> findRandomHero();
}
```

[`rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/VillainClient.java`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/VillainClient.java):

```java
public class VillainClient {
  public VillainClient(FightConfig fightConfig) {
    this.villainClient = ClientBuilder.newClient()
      .target(fightConfig.villain().clientBaseUrl())
      .path("api/villains/");
  }
  public Uni<Villain> findRandomVillain() {
    var target = this.villainClient.path("random");   // GET api/villains/random
    ...
  }
}
```

[`rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/NarrationClient.java`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/java/io/quarkus/sample/superheroes/fight/client/NarrationClient.java):

```java
@Path("/api/narration")
@RegisterRestClient(configKey = "narration-client")
public interface NarrationClient {
  @POST
  Uni<String> narrate(@SpanAttribute("arg.fight") FightToNarrate fight);
}
```

[`rest-fights/src/main/resources/application.properties`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/resources/application.properties)
(Stork static service discovery — cross-confirms each target's own port, see provider table below):

```properties
quarkus.rest-client.hero-client.url=stork://hero-service
quarkus.rest-client.narration-client.url=stork://narration-service
fight.villain.client-base-url=stork://villain-service

quarkus.stork.hero-service.service-discovery.address-list=localhost:8083
quarkus.stork.villain-service.service-discovery.address-list=localhost:8084
quarkus.stork.narration-service.service-discovery.address-list=localhost:8087
```

## Provider-side evidence (OpenAPI contracts, independent of the caller code above)

| Service | `quarkus.application.name` | HTTP port | OpenAPI file | Path / method / operationId |
|---|---|---|---|---|
| rest-heroes | `rest-heroes` | `8083` | [`rest-heroes/src/main/resources/openapi/openapi.yml`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-heroes/src/main/resources/openapi/openapi.yml) | `GET /api/heroes/random`, `operationId: getRandomHero` |
| rest-villains | `rest-villains` | `8084` | [`rest-villains/src/main/resources/openapi/openapi.yml`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-villains/src/main/resources/openapi/openapi.yml) | `GET /api/villains/random`, `operationId: getRandomVillain` |
| rest-narration | `rest-narration` | `8087` | [`rest-narration/src/main/resources/openapi/openapi.yml`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-narration/src/main/resources/openapi/openapi.yml) | `POST /api/narration`, `operationId: narrate` |
| rest-fights | `rest-fights` | `8082` | [`rest-fights/src/main/resources/openapi/openapi.yml`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/resources/openapi/openapi.yml) | `GET /api/fights/randomfighters`, `operationId: getRandomFighters` |

`quarkus.application.name` for each service, from its own `application.properties`/`application.yml`:

```properties
# rest-heroes/src/main/resources/application.yml
quarkus:
  application:
    name: rest-heroes
  http:
    port: 8083
```

```properties
# rest-villains/src/main/resources/application.properties
quarkus.application.name=rest-villains
quarkus.http.port=8084
```

```properties
# rest-narration/src/main/resources/application.properties
quarkus.application.name=rest-narration
quarkus.http.port=8087
```

The Stork static address-list ports above (`8083`, `8084`, `8087`) match each target service's own
`quarkus.http.port` exactly — the caller-side and provider-side evidence corroborate each other
independently.

## gRPC boundary evidence (mandatory `UNSUPPORTED`, I2 spec §12)

[`rest-fights/src/main/proto/locationservice-v1.proto`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/proto/locationservice-v1.proto):

```protobuf
package io.quarkus.sample.superheroes.location.v1;
```

`rest-fights/src/main/resources/application.properties`:

```properties
quarkus.grpc.clients.locations.host=localhost
quarkus.grpc.clients.locations.port=8089
```

`grpc-locations/src/main/resources/application.yml`:

```yaml
quarkus:
  application:
    name: grpc-locations
  http:
    port: 8089
```

`rest-fights` calls `grpc-locations` via gRPC, not HTTP — there is no OpenAPI contract for this
interaction and no REST operation to target. AIP v0.3 has no gRPC/protobuf ingestion adapter, so
this dependency stays outside AIP's supported semantic scope by construction.
