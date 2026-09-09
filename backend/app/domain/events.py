from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from app.domain.models import Model, new_id, utcnow

EventKind = Literal[
    "design_revision", "workforce", "predecessor", "material", "equipment", "inspection", "external"
]


class EventChange(Model):
    revision: str | None = Field(default=None, min_length=1, max_length=100)
    available_workers: int | None = Field(default=None, ge=0, le=10000)
    qualifications: tuple[str, ...] | None = None
    predecessor_id: str | None = None
    complete: bool | None = None
    resource_id: str | None = None
    available: bool | None = None
    inspection_passed: bool | None = None


class ProjectEvent(Model):
    id: str = Field(default_factory=new_id)
    project_id: str
    kind: EventKind
    work_package_id: str
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=4000)
    source: str = Field(default="local-demo", max_length=200)
    change: EventChange = Field(default_factory=EventChange)
    observed_at: AwareDatetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def validate_change(self) -> Self:
        fields = self.change.model_dump(exclude_none=True)
        required = {
            "design_revision": {"revision"},
            "workforce": {"available_workers"},
            "predecessor": {"predecessor_id", "complete"},
            "material": {"resource_id", "available"},
            "equipment": {"resource_id", "available"},
            "inspection": {"inspection_passed"},
            "external": set(),
        }[self.kind]
        allowed = required | ({"qualifications"} if self.kind == "workforce" else set())
        if not required.issubset(fields) or not set(fields).issubset(allowed):
            raise ValueError(f"{self.kind} requires {sorted(required)}; allowed: {sorted(allowed)}")
        return self
