# Controlled two-Workload acquisition

The [I1 runbook](../../docs/specifications/0.6.0/i1-capture-acquisition-runbook.md) governs this
harness. [I5 revision 0.1](../../docs/specifications/0.6.0/i5-real-system-qualification-and-product-demonstration.md)
requires a new actual recording; the committed rehearsal is preserved.

```bash
# Commit the harness first. OUT must not already exist.
bash harness/locality-capture/rehearse.sh --actual /tmp/my-i5-capture
```

Actual mode uses a unique throwaway kind cluster and app image, at least 300 seconds of overlap
traffic (330 by default) and 120 seconds after P1 removal. Resources come from Kubernetes and real
SDK-instrumented HTTP calls. It exports raw files, validates recording identities and owner chains,
and tears down only its own cluster after successful export. A failed run stops and retains its
artifacts/cluster for inspection; do not promote it or edit its recording.

Without `--actual`, the existing rehearsal invocation/defaults remain available.

C1 and C2 are storage directories. For subsequent I5.2 replay, copy the selected snapshot bytes
unchanged into **one physical root**, configured as the literal relative path `capture`, with the
registration in `source-registration.json`. Import C1 first, evaluate it before replacing it with
C2, and keep the same root/registration throughout. C2's predecessor is authored from existing pure
inventory formulas for that registration; changing the configured root would invalidate it.
Self-declared completeness and non-atomic kubectl capture are disclosed, not stronger authority.

`capture_metadata.py` authors capture envelopes and checks raw evidence; it does not ingest the
recording or query AIP answers. `replay/analyze.py` provides standalone CLIENT identity/count checks.
Acquisition acceptance is the owner's decision. Independently author and commit the actual capture's
expected facts before any AIP evaluation in I5.2; the existing rehearsal replay script and its
separate-first-import C2 behavior are not an actual-capture qualification command.
