import pytest
from app.adapters.demo import (
    LocalEquipmentReader,
    LocalGeoProvider,
    LocalInspectionReader,
    LocalMaterialReader,
    LocalScheduleReader,
    LocalWorkforceReader,
    StructuredBIMProvider,
    demo_state,
)
from app.adapters.demo_ids import DUCT_GUID, WALL_GUID
from app.adapters.schedule_local import LocalScheduleWriter
from app.domain.errors import NotFound


def test_narrow_local_readers_share_authoritative_state():
    state = demo_state()
    assert [w.id for w in LocalScheduleReader().dependencies(state, "WP-200")] == ["WP-100"]
    assert LocalWorkforceReader().availability(state, "WP-200")["available"] == 4
    assert LocalMaterialReader().materials(state, "WP-200") == {"duct-section": True}
    assert LocalEquipmentReader().equipment(state, "WP-200") == {"scissor-lift": True}
    assert LocalInspectionReader().accepted(state, "WP-200")
    before = state.model_dump_json()
    materials = LocalMaterialReader().materials(state, "WP-200")
    materials["duct-section"] = False
    assert state.model_dump_json() == before


def test_schedule_writer_is_explicit_versioned_and_idempotent():
    state = demo_state()
    writer = LocalScheduleWriter()
    updated = writer.confirm_complete(state, "WP-200")
    assert not state.package("WP-200").complete
    assert updated.package("WP-200").complete
    assert updated.version == state.version + 1
    assert updated.sources != state.sources
    assert writer.confirm_complete(updated, "WP-200") == updated
    with pytest.raises(NotFound):
        writer.confirm_complete(state, "unknown")


def test_structured_bim_targeted_query_and_geo_references():
    provider = StructuredBIMProvider()
    assert {e.id for e in provider.elements(location="L02-E")} == {DUCT_GUID, WALL_GUID}
    assert provider.elements(element_id=DUCT_GUID)[0].type == "IfcDuctSegment"
    assert provider.elements(kind="IfcWall")[0].id == WALL_GUID
    assert provider.elements(element_id="missing") == []
    features = LocalGeoProvider().features("harbor-east")
    assert features["type"] == "FeatureCollection"
    assert all(f["properties"]["project_id"] == "harbor-east" for f in features["features"])


def test_geo_clickable_points_cover_the_authoritative_work_packages():
    state = demo_state()
    features = LocalGeoProvider().features(state.project.id)["features"]
    markers = {
        feature["properties"].get("work_package_id")
        for feature in features
        if feature["geometry"]["type"] == "Point"
    }
    assert {package.id for package in state.work_packages} <= markers
    assert all(feature["properties"]["project_id"] == state.project.id for feature in features)
