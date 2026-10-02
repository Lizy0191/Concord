# Third-party notices

## IfcDiff 0.8.5

- Project: IfcDiff, distributed by the IfcOpenShell project
- Source: https://github.com/IfcOpenShell/IfcOpenShell/tree/main/src/ifcdiff
- Package: https://pypi.org/project/ifcdiff/0.8.5/
- License: GNU Lesser General Public License v3.0 or later
- Use: compares two IFC revisions and reports added, deleted, and changed GlobalIds
- Modification: none; Concord imports the published package through an adapter
- Replaceability: isolated behind `IfcComparisonEngine`; stored Concord records use project-owned models

IfcDiff is an optional BIM dependency. It is not vendored into this repository. The upstream
license and source remain available at the links above.

## IfcClash 0.8.5

- Project: IfcClash, distributed by the IfcOpenShell project
- Source: https://github.com/IfcOpenShell/IfcOpenShell/tree/16723d11cab9bc8a13b4e025a00d39445ccc462e/src/ifcclash
- Package: https://pypi.org/project/ifcclash/0.8.5/
- License: GNU Lesser General Public License v3.0 or later
- Use: targeted intersection, collision, and clearance runs behind `IfcClashAdapter`
- Modification: none; SDK records are normalized into project-owned changes and evidence

## IfcTester 0.8.5

- Project: IfcTester, distributed by the IfcOpenShell project
- Source: https://github.com/IfcOpenShell/IfcOpenShell/tree/16723d11cab9bc8a13b4e025a00d39445ccc462e/src/ifctester
- Package: https://pypi.org/project/ifctester/0.8.5/
- License: GNU Lesser General Public License v3.0 or later
- Use: IDS parsing and validation behind `IfcTesterAdapter`
- Modification: none; failures are normalized into project-owned IDS evidence

## bcf-client 0.8.5

- Project: IfcOpenShell BCF client
- Source: https://github.com/IfcOpenShell/IfcOpenShell/tree/16723d11cab9bc8a13b4e025a00d39445ccc462e/src/bcf
- Package: https://pypi.org/project/bcf-client/0.8.5/
- License: GNU General Public License v3.0
- Use: optional BCF 2.1 viewpoint read/write behind `BCFAdapter`
- Modification: none; BCF XML remains the interchange format
- Boundary: the 0.8.5 package metadata declares GPLv3; the upstream source tree also contains COPYING and COPYING.LESSER. Treat the published package as GPLv3 for this pre-integration work until the discrepancy is resolved. Optional installation does not remove license obligations. IfcTester also depends on bcf-client, so this is a BIM-extra distribution consideration, not only a BCF feature switch. No production packaging qualification is claimed here.

## RapidOCR 3.9.2

- Project: RapidOCR
- Source: https://github.com/RapidAI/RapidOCR/tree/v3.9.2
- Package: https://pypi.org/project/rapidocr/3.9.2/
- License: Apache License 2.0 (upstream project)
- Use: explicit, local, lazy-loaded Chinese OCR through Docling; model files are provisioned separately
- Modification: none; OCR confidence and source provenance remain attached to extracted chunks

## ONNX Runtime 1.24.4

- Project: ONNX Runtime
- Source: https://github.com/microsoft/onnxruntime/tree/v1.24.4
- Package: https://pypi.org/project/onnxruntime/1.24.4/
- License: MIT License
- Use: local RapidOCR execution provider
- Modification: none

## Docling 2.126.0

- Project: Docling
- Source: https://github.com/docling-project/docling
- Package: https://pypi.org/project/docling/2.126.0/
- License: MIT License (upstream project)
- Use: structured PDF, Office, CSV, Markdown, HTML, and opt-in image ingestion
- Modification: none; the Concord normalizer retains source locations and table structure

## Viewer and reference donors

The following repositories were inspected at pinned commits. They remain references in this backend prework: no drawing, CAD, or IFC Viewer Online integration is delivered yet, and no donor source is vendored.

| Repository | Revision | License | Concord use |
| --- | --- | --- | --- |
| Kentucky-ai/opentakeoff | `60c82e34b389384401a083cefeb9389f89fbaae1` | Apache-2.0 | Drawing/PDF interaction reference; no estimating model imported |
| a-subhaneel/pdf-diff-viewer | `96af1ce5caa0b27b3b4a2e14ef3c16aed0842170` | MIT | PDF visual diff integration reference |
| mlightcad/cad-viewer | `250533a861e9fa1feca739b6783286ed4e91674a` | MIT | DXF viewer/diff integration reference; no GPL DWG path enabled |
| j03rul4nd/ifc-viewer-online | `5073adf1f5fadef76129460555482b6507c2be74` | MIT | IFC viewer lifecycle and selection mapping reference |

### Native AEC connector boundary

Revit, AutoCAD, and Navisworks files are not parsed by reverse-engineered readers in Concord. A future connector must run in the host application or an approved conversion service, emit a documented artifact, and upload that artifact through `ProjectSourceRevision`. The connector boundary is informed by Speckle's public connector architecture:

- Source: https://github.com/specklesystems/speckle-sharp-connectors/tree/195556ba551be739b8313526cceea0ecb254ef72
- License: Apache-2.0
- Use: architecture reference only; Speckle Server types are not imported into Concord's domain

### DWG boundary

LibreDWG and other GPL-based DWG paths are not dependencies of Concord Core. DWG support remains an explicitly isolated optional capability or an approved native AutoCAD conversion path until licensing and distribution are separately approved.


## xmlschema 4.3.2

- Project: xmlschema
- Source: https://github.com/sissaschool/xmlschema
- Package version: `uv.lock` records the resolved version
- License: MIT
- Use: validate against IfcTester's bundled IDS XSD with local schema imports, defused XML resources and uploaded schema hints disabled
- Modification: none; IDS semantics and parsing remain in IfcTester
