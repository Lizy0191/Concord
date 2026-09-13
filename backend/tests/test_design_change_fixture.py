import pytest
from app.adapters.demo import StructuredBIMProvider
from app.adapters.demo_ids import DUCT_GUID, TRAY_GUID, WALL_GUID
from app.adapters.design_change_fixture import FIXTURE_OBSERVED_AT, design_change_state
from app.domain.errors import DomainError
from app.domain.models import ProjectSnapshot
from app.domain.readiness import evaluate


def test_design_change_state_is_deterministic_and_revisioned():
    v16 = design_change_state("V16")
    v17 = design_change_state("V17")

    assert design_change_state("V17") == v17
    assert v16.version == 1
    assert v17.version == 2
    assert v16.source("drawing").revision == v16.source("bim").revision == "V16"
    assert v17.source("drawing").revision == v17.source("bim").revision == "V17"
    assert all(source.observed_at == FIXTURE_OBSERVED_AT for source in v17.sources)
    assert v17.package("WP-200").design_revision == "V17"
    assert v17.package("WP-200").accepted_revision == "V16"


def test_v17_change_preserves_traceable_evidence():
    state = design_change_state("V17")
    snapshot = ProjectSnapshot(
        project_id=state.project.id,
        version=state.version,
        sources=state.sources,
        captured_at=FIXTURE_OBSERVED_AT,
    )
    evidence, _, constraints, _, impact = evaluate(state, snapshot)

    design = next(
        item
        for item in constraints
        if item.kind == "design" and item.work_package_id == "WP-200"
    )
    item = next(item for item in evidence if item.id == design.evidence_ids[0])
    assert item.source_id == "drawing/WP-200"
    assert item.source_revision == "V17"
    assert item.observed_at == FIXTURE_OBSERVED_AT
    assert set(item.element_ids) == {WALL_GUID, DUCT_GUID}
    assert {WALL_GUID, DUCT_GUID}.issubset(impact.element_ids)


def test_structured_bim_revisions_are_queryable_with_stable_relationships():
    v16 = {item.id: item for item in StructuredBIMProvider("V16").elements()}
    provider = StructuredBIMProvider("V17")
    v17 = {item.id: item for item in provider.elements()}

    assert set(v16) == set(v17) == {WALL_GUID, DUCT_GUID, TRAY_GUID}
    wall = provider.elements(element_id=WALL_GUID)[0]
    assert (wall.storey, wall.space, wall.revision) == ("L02-E", "L02-E-ZONE", "V17")
    assert wall.properties["Easting"] - v16[WALL_GUID].properties["Easting"] == 0.6
    assert wall.properties["ChangeStatus"] == "changed"
    assert wall.properties["WorkPackageIds"] == ("WP-100", "WP-200")
    assert v17[DUCT_GUID].properties["ChangeStatus"] == "affected"
    assert provider.elements(location="L02-E-ZONE") == [v17[WALL_GUID], v17[DUCT_GUID]]


def test_design_change_fixture_rejects_unknown_revision():
    with pytest.raises(DomainError):
        design_change_state("V18")
    with pytest.raises(DomainError):
        StructuredBIMProvider("V18")
