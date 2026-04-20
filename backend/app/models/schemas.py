from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ---------- Input ----------

class LeadInput(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000,
                         description="Raw lead message or inquiry text")
    source: Optional[str] = Field(None, max_length=200, description="Where the lead came from")
    budget: Optional[str] = Field(None, max_length=200, description="Budget if mentioned")
    service_requested: Optional[str] = Field(None, max_length=300, description="Service requested if known")
    urgency: Optional[Literal["low", "medium", "high"]] = Field(None)
    contact_name: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[str] = Field(None, max_length=200)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message cannot be empty or whitespace")
        return v.strip()


# ---------- Agent outputs ----------

class IntakeOutput(BaseModel):
    name: Optional[str] = None
    service_requested: Optional[str] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None
    budget: Optional[str] = None
    business_type: Optional[str] = None
    key_needs: List[str] = []
    clean_summary: str


class QualificationOutput(BaseModel):
    tier: Literal["High", "Medium", "Low"]
    intent_score: int = Field(..., ge=0, le=100)
    positive_signals: List[str] = []
    red_flags: List[str] = []
    reasoning: str


class ResponseOutput(BaseModel):
    tone: Literal["warm", "consultative", "brief", "urgent"]
    message: str
    cta: str


class FollowUp(BaseModel):
    when: str
    channel: Literal["email", "sms", "call", "linkedin"]
    message: str


class FollowUpOutput(BaseModel):
    follow_up_needed: bool
    strategy: str
    messages: List[FollowUp] = []


class ActionOutput(BaseModel):
    next_action: Literal[
        "book_call",
        "send_pricing",
        "escalate_to_sales",
        "nurture_later",
        "do_not_prioritize",
    ]
    priority: Literal["P0", "P1", "P2", "P3"]
    justification: str
    estimated_pipeline_value_usd: int = Field(
        0, ge=0,
        description="Best-effort dollar estimate of pipeline this lead represents"
    )


# ---------- Final combined output ----------

class AgentLog(BaseModel):
    agent: str
    status: Literal["ok", "error"]
    duration_ms: int
    note: Optional[str] = None


class FinalDecisionOutput(BaseModel):
    lead_input: LeadInput
    intake: IntakeOutput
    qualification: QualificationOutput
    response: ResponseOutput
    follow_up: FollowUpOutput
    action: ActionOutput
    manager_summary: str
    logs: List[AgentLog]
