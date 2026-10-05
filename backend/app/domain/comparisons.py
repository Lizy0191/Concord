"""Requests identify originals; only registered workers may produce comparison facts."""

import json
from typing import Literal

from pydantic import Field, model_validator

from app.domain.models import Model
from app.domain.project_sources import ProjectSourceRevision


class ComparisonRequest(Model):
    kind: Literal["pdf_comparison", "cad_comparison"]
    operation_id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    from_revision_id: str = Field(min_length=1, max_length=100)
    to_revision_id: str = Field(min_length=1, max_length=100)
    options: dict[str, object] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="after")
    def bounded_options(self):
        try:
            encoded = json.dumps(self.options, sort_keys=True, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise ValueError("Comparison options must be finite JSON") from exc
        if len(encoded.encode("utf-8")) > 16384:
            raise ValueError("Comparison options exceed 16 KiB")
        return self


class BoundComparison(ComparisonRequest):
    engine: str = Field(min_length=1, max_length=100)
    engine_version: str = Field(min_length=1, max_length=240)
    revisions: tuple[ProjectSourceRevision, ProjectSourceRevision]
