from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class ActionRequest(BaseModel):
    """A proposed agent action submitted for evaluation."""
    agent_id: str = Field(..., description="Identity of the acting agent")
    principal: Optional[str] = Field(None, description="Owning org/team, e.g. 'org:acme:finance'")
    framework: Optional[str] = Field(None, description="Agent framework in use, e.g. 'langchain', 'custom'")
    action_type: str = Field(..., description="e.g. 'wire_transfer', 'delete_vm', 'read_ehr'")
    consequence_class: str = Field(
        ..., description="e.g. financial_transfer, infra_change, health_record_access, generic_tool_call, low_risk"
    )
    purpose: Optional[str] = Field(None, description="Stated purpose/justification for the action")
    consumer: Optional[str] = Field(None, description="Who/what receives the effect of this action")
    jurisdiction: Optional[str] = Field(None, description="Applicable jurisdiction, e.g. 'US', 'EU'")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    policy_pack: str = Field("generic", description="Which policy pack to evaluate against")
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of registered evidence packages this action relies on")


class PolicyDecision(BaseModel):
    decision: Literal["allow", "deny", "conditional"]
    reasons: list[str]
    policy_pack: str
    policy_pack_version: str
    matched_rules: list[str]


class AgentInfo(BaseModel):
    agent_id: str
    principal: Optional[str] = None
    framework: Optional[str] = None


class ActionInfo(BaseModel):
    type: str
    consequence_class: str
    consequence_score: float
    score_factors: List[str]
    parameters_hash: str


class PolicyInfo(BaseModel):
    policy_pack: str
    policy_pack_version: str
    matched_rules: List[str]
    reasons: List[str]


class EvidenceInfo(BaseModel):
    evidence_refs: List[str] = Field(default_factory=list)


class SignatureInfo(BaseModel):
    alg: Literal["Ed25519"] = "Ed25519"
    key_id: str
    value: str


class Receipt(BaseModel):
    """
    Independently verifiable action receipt.

    Verification does not require trusting Cyraduct's server: fetch the
    public key from /v1/public-key and verify `signature.value` against
    the canonical hash of {receipt_id, action_hash, expires_at} yourself
    (see verify_receipt.py in the repo root for a standalone example).
    """
    receipt_id: str
    action_id: str
    decision: Literal["allow", "conditional"]  # denies never get a receipt
    agent: AgentInfo
    action: ActionInfo
    policy: PolicyInfo
    evidence: EvidenceInfo
    issued_at: str
    expires_at: str
    action_hash: str
    prev_receipt_hash: Optional[str] = None  # chains receipts per agent for tamper evidence
    signature: SignatureInfo
    revoked: bool = False


class VerifyResult(BaseModel):
    valid: bool
    reason: str
    receipt: Optional[Receipt] = None


class EvidencePackage(BaseModel):
    evidence_id: str
    label: str = Field(..., description="e.g. 'soc2_type2', 'model_card_v3', 'human_approval'")
    content_hash: str = Field(..., description="SHA-256 hash of the underlying evidence document")
    registered_at: str
    registered_by: Optional[str] = None


class EvidenceRegisterRequest(BaseModel):
    label: str
    content_hash: str
    registered_by: Optional[str] = None
