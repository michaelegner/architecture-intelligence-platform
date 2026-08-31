# Upstream Identity — `<system-id>`

Required fields (I1 §8):

```text
system:              <system-id>
repository:           <upstream repository URL>
project version/tag:  <tag, if applicable>
commit:               <full commit SHA>
validation profile revision: <this dossier's own revision/commit>
validation date:      <YYYY-MM-DD>
```

## License

```text
upstream license:     <license name/identifier>
```

AIP does not vendor the complete upstream repository — only minimal derived metadata and legally
reusable fixtures are committed (parent spec §36).

## Notes

A validation result applies only to the pinned commit above. Changing the pinned revision
invalidates the previous qualifying comparison until revalidated (I1 §8).
