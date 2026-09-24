# Upstream Identity — `<system-id>` (v0.5.0)

I5 spec §5 requires these fields. Reconfirm every one before the first qualifying comparison. A
changed pin requires a documented reason, a fresh ground-truth review, and a new freeze.

```text
system:                      <system-id>
repository:                  <upstream repository URL>
project version/tag:         <tag, if applicable>
commit:                      <full commit SHA>
image digests:               <image@sha256:... per started image, if applicable>
dependency/runtime identity: <e.g. framework/provider versions that bound the profile>
validation profile revision: <this dossier's own revision/commit>
validation date:             <YYYY-MM-DD>
```

## Upstream Kubernetes manifests (I5 §5; Quarkus only)

```text
present at the pinned commit: <yes | no — if no, record the §9 coverage gap; never author substitutes>
paths:                        <upstream paths, e.g. deploy/k8s/...>
sha256 per file:              <digest per manifest file>
service-id annotations:       <per in-scope Workload: present and Path A-evaluable, or absent>
```

## License

```text
upstream license:     <license name/identifier>
```

AIP does not vendor the complete upstream repository. It commits only minimal derived metadata and
legally reusable fixtures.

## Notes

A validation result applies only to the pinned identities above. v0.3 results for this system are
research input only, never v0.5 qualification results (I5 §5).
