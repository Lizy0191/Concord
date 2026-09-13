"""Real optional SDK tests. Missing packages produce explicit skips, not fake passes."""

import hashlib
from pathlib import Path

import pytest
from app.adapters.bim_ifc import IfcOpenShellBIMProvider, LocalIFCImporter
from app.adapters.demo import StructuredBIMProvider
from app.adapters.demo_ids import DUCT_GUID, TRAY_GUID, WALL_GUID
from app.adapters.documents_docling import DoclingDocumentParser
from app.adapters.ifc_fixture import generate_ifc_fixture
from app.adapters.resolver_ortools import ORToolsResolver
from app.adapters.scheduling_fixture import coordination_fixture
from app.domain.errors import ProviderError
from app.domain.scheduling import validate_solution

pytestmark = pytest.mark.integration


def test_real_ortools_capacity_precedence_and_qualification():
    pytest.importorskip("ortools")
    problem = coordination_fixture()
    result = ORToolsResolver().solve(problem)
    assert result.status == "OPTIMAL"
    assert result.makespan == 9  # Seven exclusive lift hours, then two inspection hours.
    validate_solution(problem, result)
    assert result.proposal_only


def test_real_ortools_explicit_infeasible_window():
    pytest.importorskip("ortools")
    problem = coordination_fixture()
    tasks = tuple(task.model_copy(update={"latest_end": 6}) for task in problem.tasks)
    constrained = problem.model_copy(update={"tasks": tasks})
    result = ORToolsResolver().solve(constrained)
    assert result.status == "INFEASIBLE"
    assert not result.assignments


def test_real_ifc_fixture_queries_and_geometry(tmp_path):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    import ifcopenshell.geom as ifc_geom
    import ifcopenshell.validate as ifc_validate

    v16_path = generate_ifc_fixture(tmp_path / "fixture-v16.ifc", revision="V16")
    v17_path = generate_ifc_fixture(tmp_path / "fixture-v17.ifc", revision="V17")
    provider = IfcOpenShellBIMProvider(v16_path)
    elements = provider.elements()
    assert {e.id for e in elements} == {WALL_GUID, DUCT_GUID, TRAY_GUID}
    assert {e.id for e in provider.elements(location="L02-E")} == {WALL_GUID, DUCT_GUID}
    assert provider.elements(element_id=DUCT_GUID)[0].type == "IfcDuctSegment"
    assert len(provider.by_property("CCA_Coordination", "DrawingRevision", "V16")) == 3
    assert {e.id for e in provider.elements(location="L02-E-ZONE")} == {WALL_GUID, DUCT_GUID}
    assert all(e.revision == hashlib.sha256(v16_path.read_bytes()).hexdigest() for e in elements)
    assert {e.id for e in LocalIFCImporter().parse(v16_path.read_bytes())} == {
        e.id for e in elements
    }
    # Shared contract: stable IDs, types and spatial locations, not identical property
    # serialization.
    structured = {e.id: e for e in StructuredBIMProvider().elements()}
    for element in elements:
        assert (element.type, element.storey) == (
            structured[element.id].type,
            structured[element.id].storey,
        )
    models = [ifcopenshell.open(str(path)) for path in (v16_path, v17_path)]
    for model in models:
        logger = ifcopenshell.validate.json_logger()
        ifc_validate.validate(model, logger)
        assert not logger.statements, logger.statements
        shape = ifc_geom.create_shape(ifc_geom.settings(), model.by_guid(WALL_GUID))
        assert len(shape.geometry.verts) > 0
    v17_provider = IfcOpenShellBIMProvider(v17_path)
    changed_wall = v17_provider.elements(element_id=WALL_GUID)[0]
    assert changed_wall.space == "L02-E-ZONE"
    assert changed_wall.properties["CCA_Coordination"]["DrawingRevision"] == "V17"
    assert changed_wall.properties["CCA_Coordination"]["ChangeStatus"] == "changed"
    assert (
        models[1].by_guid(WALL_GUID).ObjectPlacement.RelativePlacement.Location.Coordinates[0]
        == 0.6
    )


def test_real_ifc_rejects_malformed_input(tmp_path):
    pytest.importorskip("ifcopenshell")
    path = tmp_path / "bad.ifc"
    path.write_text("not an IFC file")
    with pytest.raises(ProviderError):
        IfcOpenShellBIMProvider(path).elements()


def test_real_docling_preserves_source_and_item_location():
    pytest.importorskip("docling")
    path = Path(__file__).resolve().parents[3] / "fixtures" / "coordination-notice.html"
    chunks = DoclingDocumentParser().parse(path.read_bytes(), path.name)
    assert any("V17" in c.text for c in chunks)
    assert all(c.source_hash == hashlib.sha256(path.read_bytes()).hexdigest() for c in chunks)
    assert all(c.location and c.parser == "docling-local-no-ocr" for c in chunks)
    assert all(c.page is None for c in chunks)  # HTML has no real physical pages.


def test_real_docling_pdf_preserves_physical_pages_and_rejects_truncation():
    pytest.importorskip("docling")
    path = Path(__file__).resolve().parents[3] / "fixtures/coordination-notice.pdf"
    content = path.read_bytes()
    chunks = DoclingDocumentParser().parse(content, path.name)
    assert any("PDF-PAGE-ONE-V17" in chunk.text and chunk.page == 1 for chunk in chunks)
    assert any("PDF-PAGE-TWO-QC" in chunk.text and chunk.page == 2 for chunk in chunks)
    assert all(chunk.source_hash == hashlib.sha256(content).hexdigest() for chunk in chunks)
    assert all(chunk.location and chunk.parser == "docling-local-no-ocr" for chunk in chunks)
    with pytest.raises(ProviderError):
        DoclingDocumentParser(max_pages=1).parse(content, path.name)
