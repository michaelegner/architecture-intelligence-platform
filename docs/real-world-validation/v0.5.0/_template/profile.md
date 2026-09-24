# Validation Profile — `<system-id>` (v0.5.0)

The bounded, reproducible profile actually exercised (I5 §6 item 1).

## Input classification (I5 §6)

Each input must fall into exactly one of three kinds. An input of one kind is never presented as
another kind.

| Input | Kind | Path / digest |
| --- | --- | --- |
| <e.g. upstream OpenAPI> | upstream-supplied | <path, sha256> |
| <e.g. OTLP from the running system> | independently captured | <collector config, window> |
| <e.g. Path B mapping artifact> | AIP operator configuration (never ground truth) | <path, sha256> |

## Components/processes started

<!-- which services/processes are started; exclusions -->

## Runtime/deployment mode

## Telemetry configuration

<!-- standard OTel export/OTLP/Collector config only -->

## Architecture flows exercised

## Supported AIP semantics in scope

<!-- the I5 §7 fact classes this profile validates, per the frozen I5 §8 scope -->

## Known upstream mechanisms out of scope

## Comparison projection, window, and determinism (I5 §6 item 4, §12)

```text
observation environment:        <environment name>
observation window:             <window_start> .. <window_end>
absolute checkout location:     <the one absolute path both byte-identity runs use>
normalization policy:           <ordering / capture / time-dependent fields only; never location>
rerun criteria:                 <when a comparison is rerun>
```

## Startup, traffic, and shutdown procedures

<!-- ordered steps; how to reset upstream, broker, AIP graph, and telemetry state to clean -->
