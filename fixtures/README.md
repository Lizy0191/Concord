# Original synthetic fixtures

`coordination-notice.html` is an original, text-bearing construction notice for the
real Docling integration test. HTML has no physical page numbers; the parser must
preserve the source hash and item location rather than inventing pages.

Generate the original IFC4 geometry fixture:

```sh
uv run --extra bim python scripts/generate_ifc_fixture.py
```

This uses IfcOpenShell's actual authoring API to create a project/site/building,
two storeys and spaces, a wall, a duct, a cable tray, swept geometry, placements,
and property sets. Element GlobalIds match `backend/app/adapters/demo_ids.py`. The
outputs are `fixtures/harbor-east-v16.ifc` and `fixtures/harbor-east-v17.ifc`.
V17 moves the wall 0.6 metres east and marks its related duct as affected while
preserving stable identifiers, locations, work-package links, and source revisions.
Import either revision in the BIM workspace, then select the WP-200 work package or
its constraints to highlight the matching elements.

The geometry is for viewer/relationship testing, not fabrication or engineering
validation. No third-party model assets are copied. The original fixture content is
included subject to the project's pending licensing determination. Generation and
SDK-level validation are separate from the default structured-provider tests; see the
verification report for what was actually executed in the delivery environment.
