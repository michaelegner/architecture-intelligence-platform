"""v0.7.0 I1.2 internal, source-owned API-contract carriers - never canonical entities with
relations, never public properties (I1.1 contract §3, §6).

The OpenAPI adapter always builds these from its own document; the orchestrator keeps them only for
an import request that configures at least one gateway source (I1 §3.6 as amended by the owner on
2026-10-12). Association is not equivalence: a contract version is *declared for* a Service and an
Operation *belongs to* a contract version, each carried as an id-valued property with evidence ids,
never as a graph edge to a public entity. An `Operation` id is never changed by any of this.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.common.encoding import length_delimited, sha256_hex, utf8

API_CONTRACT_LABEL = "ApiContract"
API_CONTRACT_VERSION_LABEL = "ApiContractVersion"
API_CONTRACT_ASSOCIATION_LABEL = "ApiContractAssociation"

# I1.1 contract §3: an absent, empty or non-string `info.version` mints no ApiContractVersion.
CONTRACT_VERSION_LIMITATION = "CONTRACT_VERSION_MISSING_OR_NOT_STRING"

ApiContractAssociationKind = Literal[
    "OPERATION_IN_CONTRACT_VERSION", "CONTRACT_VERSION_DECLARED_FOR_SERVICE"
]


def api_contract_id(openapi_source_instance_id: str) -> str:
    """`api-contract:owned:<sha256(ld(OpenAPI SourceInstanceId))>` (contract §3, vector V08)."""
    return f"api-contract:owned:{sha256_hex(length_delimited(utf8(openapi_source_instance_id)))}"


def api_contract_version_id(contract_id: str, info_version: str) -> str:
    """`api-contract-version:owned:<sha256(ld(contract id, info.version))>` (vector V09). The caller
    passes only a non-empty `info.version` string."""
    key = length_delimited(utf8(contract_id), utf8(info_version))
    return f"api-contract-version:owned:{sha256_hex(key)}"


def api_contract_association_id(
    kind: ApiContractAssociationKind, contract_version_id: str, target_id: str
) -> str:
    key = length_delimited(utf8(kind), utf8(contract_version_id), utf8(target_id))
    return f"api-contract-association:owned:{sha256_hex(key)}"


class ApiContract(BaseModel):
    id: str = Field(min_length=1)
    openapi_source_instance_id: str = Field(min_length=1)
    # Sorted limitation codes (contract §3); empty when the contract has a usable version.
    limitations: list[str] = Field(default_factory=list)


class ApiContractVersion(BaseModel):
    id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    info_version: str = Field(min_length=1)


class ApiContractAssociation(BaseModel):
    id: str = Field(min_length=1)
    kind: ApiContractAssociationKind
    contract_version_id: str = Field(min_length=1)
    # The Operation id for OPERATION_IN_CONTRACT_VERSION, the Service id for
    # CONTRACT_VERSION_DECLARED_FOR_SERVICE.
    target_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
