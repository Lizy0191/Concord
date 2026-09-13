from app.adapters.demo_ids import DUCT_GUID, TRAY_GUID, WALL_GUID
from app.domain.errors import DomainError
from app.domain.models import Area, Project, ProjectState, SourceRevision, WorkPackage
from app.ports.providers import BIMElement

PROJECT_ID = "harbor-east"


def demo_state(version: int = 1) -> ProjectState:
    return ProjectState(
        project=Project(
            id=PROJECT_ID,
            name="Harbor East / Building A",
            description="Synthetic construction coordination reference project",
        ),
        version=version,
        areas=(
            Area(id="L02-E", name="Level 02 / East wing", floor="02"),
            Area(id="L03-E", name="Level 03 / East wing", floor="03"),
        ),
        sources=tuple(
            SourceRevision(source=name, revision=f"r{version}")
            for name in [
                "drawing",
                "bim",
                "schedule",
                "workforce",
                "material",
                "equipment",
                "inspection",
            ]
        ),
        work_packages=(
            WorkPackage(
                id="WP-100",
                name="Structure handover",
                area_id="L02-E",
                discipline="Structure",
                complete=True,
                element_ids=(WALL_GUID,),
                owner="Structure / Lin",
            ),
            WorkPackage(
                id="WP-200",
                name="East-wing duct installation",
                area_id="L02-E",
                discipline="Mechanical",
                element_ids=(DUCT_GUID, WALL_GUID),
                predecessors=("WP-100",),
                required_workers=4,
                available_workers=4,
                required_qualifications=("duct-install",),
                qualifications=("duct-install",),
                materials={"duct-section": True},
                equipment={"scissor-lift": True},
                owner="Mechanical / Chen",
            ),
            WorkPackage(
                id="WP-300",
                name="Level 03 electrical rough-in",
                area_id="L03-E",
                discipline="Electrical",
                element_ids=(TRAY_GUID,),
                required_workers=3,
                available_workers=3,
                required_qualifications=("electrician",),
                qualifications=("electrician",),
                materials={"cable-tray": True},
                equipment={"mobile-platform": True},
                owner="Electrical / Wang",
            ),
        ),
    )


class StructuredBIMProvider:
    def __init__(self, revision: str = "V16") -> None:
        if revision not in {"V16", "V17"}:
            raise DomainError("Structured BIM fixture supports only V16 or V17")
        changed = revision == "V17"
        self.items = [
            BIMElement(
                id=WALL_GUID,
                name="East core wall",
                type="IfcWall",
                storey="L02-E",
                space="L02-E-ZONE",
                revision=revision,
                properties={
                    "FireRating": "120 min",
                    "Width": 0.2,
                    "Easting": 0.6 if changed else 0.0,
                    "ChangeStatus": "changed" if changed else "baseline",
                    "WorkPackageIds": ("WP-100", "WP-200"),
                },
                related_ids=(DUCT_GUID,),
            ),
            BIMElement(
                id=DUCT_GUID,
                name="Supply duct E-01",
                type="IfcDuctSegment",
                storey="L02-E",
                space="L02-E-ZONE",
                revision=revision,
                properties={
                    "Width": 0.6,
                    "Height": 0.4,
                    "ChangeStatus": "affected" if changed else "baseline",
                    "WorkPackageIds": ("WP-200",),
                },
                related_ids=(WALL_GUID,),
            ),
            BIMElement(
                id=TRAY_GUID,
                name="Cable tray E-01",
                type="IfcCableCarrierSegment",
                storey="L03-E",
                space="L03-E-ZONE",
                revision=revision,
                properties={
                    "Width": 0.3,
                    "ChangeStatus": "unchanged" if changed else "baseline",
                    "WorkPackageIds": ("WP-300",),
                },
            ),
        ]

    def elements(
        self, *, element_id: str | None = None, kind: str | None = None, location: str | None = None
    ) -> list[BIMElement]:
        return [
            e
            for e in self.items
            if (not element_id or e.id == element_id)
            and (not kind or e.type == kind)
            and (not location or e.storey == location or e.space == location)
        ]


class LocalScheduleReader:
    def dependencies(self, state: ProjectState, work_package_id: str) -> tuple[WorkPackage, ...]:
        return tuple(state.package(i) for i in state.package(work_package_id).predecessors)


class LocalWorkforceReader:
    def availability(self, state: ProjectState, work_package_id: str) -> dict:
        wp = state.package(work_package_id)
        return {
            "available": wp.available_workers,
            "required": wp.required_workers,
            "qualifications": wp.qualifications,
        }


class LocalMaterialReader:
    def materials(self, state: ProjectState, work_package_id: str) -> dict[str, bool]:
        return dict(state.package(work_package_id).materials)


class LocalEquipmentReader:
    def equipment(self, state: ProjectState, work_package_id: str) -> dict[str, bool]:
        return dict(state.package(work_package_id).equipment)


class LocalInspectionReader:
    def accepted(self, state: ProjectState, work_package_id: str) -> bool:
        return state.package(work_package_id).inspection_passed


class LocalGeoProvider:
    def features(self, project_id: str) -> dict:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Building A",
                        "project_id": project_id,
                        "work_package_id": "WP-200",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [120.3600, 36.0700],
                                [120.3610, 36.0700],
                                [120.3610, 36.0707],
                                [120.3600, 36.0707],
                                [120.3600, 36.0700],
                            ]
                        ],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"name": "Site access", "project_id": project_id},
                    "geometry": {"type": "Point", "coordinates": [120.3598, 36.0699]},
                },
                # Explicit selectable markers bind the map to the same work-package IDs.
                # The building polygon alone is not selectable by the Point layer.
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Duct installation",
                        "project_id": project_id,
                        "work_package_id": "WP-200",
                    },
                    "geometry": {"type": "Point", "coordinates": [120.36, 36.07]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Electrical installation",
                        "project_id": project_id,
                        "work_package_id": "WP-300",
                    },
                    "geometry": {"type": "Point", "coordinates": [120.3606, 36.0704]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Structural preparation",
                        "project_id": project_id,
                        "work_package_id": "WP-100",
                    },
                    "geometry": {"type": "Point", "coordinates": [120.3603, 36.0706]},
                },
            ],
        }
