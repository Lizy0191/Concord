"""Generate original synthetic geometry with IfcOpenShell, not a custom IFC writer.

No SDK implementation or third-party model is copied into this fixture. The
GlobalIds match the structured demo provider, so graph selection can highlight
these exact elements in the browser viewer.
"""

from pathlib import Path

from app.adapters.demo_ids import DUCT_GUID, TRAY_GUID, WALL_GUID
from app.domain.errors import CapabilityUnavailable


def generate_ifc_fixture(destination: Path) -> Path:
    try:
        import ifcopenshell.api
        import numpy as np
    except ImportError as exc:
        raise CapabilityUnavailable("Install the bim extra to generate the IFC fixture") from exc

    run = ifcopenshell.api.run
    model = run("project.create_file", version="IFC4")
    project = run(
        "root.create_entity", model, ifc_class="IfcProject", name="CCA Synthetic Harbor East"
    )
    units = [
        run("unit.add_si_unit", model, unit_type=kind)
        for kind in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT")
    ]
    run("unit.assign_unit", model, units=units)
    context = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Synthetic site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Building A")
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    floors = {}
    for name, elevation in (("L02-E", 3.6), ("L03-E", 7.2)):
        floor = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=name)
        floor.Elevation = elevation
        run("aggregate.assign_object", model, products=[floor], relating_object=building)
        floors[name] = floor

    specs = (
        (WALL_GUID, "IfcWall", "East core wall", "L02-E", (8.0, 0.2, 3.2), (0, 0, 3.6)),
        (DUCT_GUID, "IfcDuctSegment", "Supply duct E-01", "L02-E", (6.0, 0.6, 0.4), (1, 0.8, 6.2)),
        (
            TRAY_GUID,
            "IfcCableCarrierSegment",
            "Cable tray E-01",
            "L03-E",
            (6.0, 0.3, 0.15),
            (1, 0.8, 9.8),
        ),
    )
    for guid, kind, name, floor_id, dimensions, position in specs:
        element = run("root.create_entity", model, ifc_class=kind, name=name)
        element.GlobalId = guid
        run(
            "spatial.assign_container",
            model,
            products=[element],
            relating_structure=floors[floor_id],
        )
        # The representation is a simple swept rectangular prism, not detailed fabrication geometry.
        length, thickness, height = dimensions
        representation = run(
            "geometry.add_wall_representation",
            model,
            context=body,
            length=length,
            thickness=thickness,
            height=height,
        )
        run("geometry.assign_representation", model, product=element, representation=representation)
        matrix = np.eye(4)
        matrix[:3, 3] = position
        run("geometry.edit_object_placement", model, product=element, matrix=matrix, is_si=True)
        pset = run("pset.add_pset", model, product=element, name="CCA_Coordination")
        run(
            "pset.edit_pset",
            model,
            pset=pset,
            properties={
                "DrawingRevision": "V16",
                "Synthetic": True,
                "Area": floor_id,
                "Width": thickness,
                "Height": height,
            },
        )
    model.header.file_description.description = ("ViewDefinition [DesignTransferView]",)
    destination.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(destination))
    return destination
