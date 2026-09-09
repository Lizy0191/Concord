from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.domain.models import Model, new_id, utcnow


class Effect(Model):
    kind: Literal[
        "acknowledge_design",
        "assign_crew",
        "confirm_qualification",
        "confirm_predecessor",
        "confirm_material",
        "confirm_equipment",
        "record_inspection",
    ]
    work_package_id: str
    value: str | int | bool | tuple[str, ...]
    resource_id: str | None = None

    @model_validator(mode="after")
    def validate_value(self):
        if self.kind == "acknowledge_design" and (
            not isinstance(self.value, str) or not self.value
        ):
            raise ValueError("Design acknowledgement requires a revision string")
        if self.kind == "assign_crew" and (
            type(self.value) is not int or not 0 <= self.value <= 10000
        ):
            raise ValueError("Crew assignment requires a bounded nonnegative integer")
        if self.kind == "confirm_qualification" and not isinstance(self.value, tuple):
            raise ValueError("Qualifications must be a tuple of qualification identifiers")
        if (
            self.kind
            in {"confirm_predecessor", "confirm_material", "confirm_equipment", "record_inspection"}
            and self.value is not True
        ):
            raise ValueError(
                "Confirmation effects require true; negative observations must use event ingestion"
            )
        if (
            self.kind in {"confirm_predecessor", "confirm_material", "confirm_equipment"}
            and not self.resource_id
        ):
            raise ValueError("A scoped resource identifier is required")
        return self


class ResolutionOption(Model):
    id: str = Field(default_factory=new_id)
    title: str
    explanation: str
    constraint_ids: tuple[str, ...]
    effects: tuple[Effect, ...]
    resolver: str = "simple"


class ActionProposal(Model):
    id: str = Field(default_factory=new_id)
    operation_id: str = Field(default_factory=new_id)
    project_id: str
    run_id: str
    generation: int = Field(default=0, ge=0)
    snapshot_id: str
    snapshot_version: int
    work_package_id: str
    title: str
    risk: int = Field(ge=0, le=5)
    resolution: ResolutionOption
    evidence_ids: tuple[str, ...]
    execution_mode: Literal["simulated", "external"] = "simulated"
    created_at: AwareDatetime = Field(default_factory=utcnow)


class Principal(Model):
    id: str
    role: Literal["viewer", "coordinator", "approver", "safety_approver", "admin"]


class Approval(Model):
    id: str = Field(default_factory=new_id)
    proposal_id: str
    principal_id: str
    principal_role: str
    level: Literal["standard", "strong"]
    confirmation: str = ""
    created_at: AwareDatetime = Field(default_factory=utcnow)


class ActionExecution(Model):
    operation_id: str
    proposal_id: str
    project_id: str
    before_version: int
    after_version: int
    status: Literal["VERIFIED"] = "VERIFIED"
    mode: Literal["simulated", "external"]
    principal_id: str
    result: str
    executed_at: AwareDatetime = Field(default_factory=utcnow)


class AuditRecord(Model):
    id: str = Field(default_factory=new_id)
    project_id: str
    action: str
    actor: str
    run_id: str | None = None
    snapshot_id: str | None = None
    operation_id: str | None = None
    detail: dict[str, str | int | bool | None] = Field(default_factory=dict)
    created_at: AwareDatetime = Field(default_factory=utcnow)
