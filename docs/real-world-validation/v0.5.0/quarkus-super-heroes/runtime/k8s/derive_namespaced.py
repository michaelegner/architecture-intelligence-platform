"""I5 spec §5's one permitted transform: inject `metadata.namespace` into the upstream Quarkus
manifest, and change nothing else.

    uv run python derive_namespaced.py unmodified/java25-kubernetes.yml \
        namespaced/java25-kubernetes.namespaced.yml

The transform is textual, so every other byte of the upstream file survives: after each
top-level `metadata:` line it inserts `  namespace: quarkus-super-heroes`. It then proves its own
claim by parsing both files and checking that removing the injected key restores every document
exactly. It fails, and writes nothing, when:
- the source digest is not the frozen upstream digest;
- a document already declares a namespace;
- a document is cluster-scoped;
- the document and `metadata:` line counts disagree.
"""

import hashlib
import sys
from pathlib import Path

import yaml

NAMESPACE = "quarkus-super-heroes"
UPSTREAM_SHA256 = "a1cd818385b3bbb582be12d5e43960f3f1ce85a619e5a974bc5c3b03c94d2c25"
INJECTED_LINE = f"  namespace: {NAMESPACE}"
# Cluster-scoped kinds a namespace must never be injected into. None occurs in the pinned file.
CLUSTER_SCOPED_KINDS = frozenset(
    {"Namespace", "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition", "Node"}
)


def derive(source_text: str) -> str:
    lines = source_text.split("\n")
    out: list[str] = []
    for line in lines:
        out.append(line)
        if line == "metadata:":
            out.append(INJECTED_LINE)
    return "\n".join(out)


def _documents(text: str) -> list[dict]:
    return [doc for doc in yaml.safe_load_all(text) if doc is not None]


def verify(source_text: str, derived_text: str) -> None:
    source_docs = _documents(source_text)
    derived_docs = _documents(derived_text)
    metadata_lines = source_text.split("\n").count("metadata:")
    if len(source_docs) != metadata_lines or len(derived_docs) != len(source_docs):
        raise SystemExit("document count does not match top-level metadata: line count")
    for source_doc, derived_doc in zip(source_docs, derived_docs, strict=True):
        if source_doc["kind"] in CLUSTER_SCOPED_KINDS:
            raise SystemExit(f"cluster-scoped kind {source_doc['kind']} in source")
        if "namespace" in source_doc["metadata"]:
            raise SystemExit("source document already declares metadata.namespace")
        if derived_doc["metadata"].get("namespace") != NAMESPACE:
            raise SystemExit("derived document lacks the injected namespace")
        restored = dict(derived_doc)
        restored["metadata"] = {
            key: value for key, value in derived_doc["metadata"].items() if key != "namespace"
        }
        if restored != source_doc:
            raise SystemExit("derived document differs from source beyond the namespace")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    source_path, target_path = Path(argv[1]), Path(argv[2])
    source_bytes = source_path.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != UPSTREAM_SHA256:
        raise SystemExit("source is not the frozen upstream deploy/k8s/java25-kubernetes.yml")
    source_text = source_bytes.decode("utf-8")
    derived_text = derive(source_text)
    verify(source_text, derived_text)
    target_path.write_bytes(derived_text.encode("utf-8"))
    print(hashlib.sha256(derived_text.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
