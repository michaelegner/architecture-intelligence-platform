"""Separate, offline-fixture-producing capture tools for gateway sources (v0.7.0 I1.3). Nothing in
`app.ingestion`, `app.graph` or any adapter may import this package: the replay adapter consumes the
normalized fixture only and never contacts a gateway (I1 spec §3.2)."""
