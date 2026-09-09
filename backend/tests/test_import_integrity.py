"""Executable local integrity contracts; external document/model SDKs are not faked as live."""

import hashlib
import io
from enum import StrEnum
from types import SimpleNamespace

import pytest
from app.adapters.documents_docling import DoclingDocumentParser, normalize_conversion
from app.adapters.vision_sanitize import clean_image
from app.domain.errors import DomainError, ProviderError
from PIL import Image


@pytest.mark.parametrize(
    "status", ["partial_success", "failure", "pending", "started", "skipped", None]
)
def test_docling_partial_or_failed_output_is_not_published(status):
    with pytest.raises(ProviderError, match="did not fully succeed"):
        normalize_conversion(SimpleNamespace(status=status, document=object()), "source-hash")


def test_docling_complete_conversion_preserves_original_hash():
    class Status(StrEnum):
        SUCCESS = "success"

    item = SimpleNamespace(text="Complete document evidence", prov=[], self_ref="#/texts/0")
    document = SimpleNamespace(iterate_items=lambda: [(item, 0)])
    chunks = normalize_conversion(
        SimpleNamespace(status=Status.SUCCESS, document=document), "original-hash"
    )
    assert len(chunks) == 1 and chunks[0].source_hash == "original-hash"
    assert chunks[0].page is None


@pytest.mark.parametrize("filename", ["source.txt", "source.csv", "source.log"])
def test_advanced_parser_keeps_real_lightweight_text_support(filename):
    content = b"Original plaintext evidence"
    chunks = DoclingDocumentParser().parse(content, filename)
    assert chunks[0].parser == "lightweight/1"
    assert chunks[0].source_hash == hashlib.sha256(content).hexdigest()


def test_vision_sanitizer_rejects_unadvertised_image_format():
    output = io.BytesIO()
    Image.new("RGB", (20, 20)).save(output, "TIFF")
    with pytest.raises(DomainError, match="actually decode"):
        clean_image(output.getvalue())


def test_real_image_resize_orientation_and_metadata_removal():
    output = io.BytesIO()
    image = Image.new("RGB", (2000, 1000))
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private description"
    image.save(output, "JPEG", exif=exif)
    with Image.open(io.BytesIO(clean_image(output.getvalue()))) as sanitized:
        assert sanitized.size == (800, 1600)
        assert sanitized.format == "PNG" and sanitized.mode == "RGB"
        assert not sanitized.getexif() and not sanitized.info


def ifc_adapter_rows(count, max_elements=2):
    """Small boundary double; this does not parse real IFC or stand in for its SDK test."""
    from app.adapters.bim_ifc import IfcOpenShellBIMProvider

    class Element:
        def __init__(self, number):
            self.GlobalId, self.Name = str(number), f"Element {number}"

        def is_a(self, kind=None):
            return kind in {"IfcElement", "IfcWall"} if kind else "IfcWall"

    rows = [Element(i) for i in range(count)]
    provider = IfcOpenShellBIMProvider(None, max_elements=max_elements)
    provider._model = SimpleNamespace(
        by_type=lambda _: rows, by_guid=lambda identity: rows[int(identity)]
    )
    provider._util = SimpleNamespace(
        get_container=lambda *args, **kwargs: None,
        get_decomposition=lambda _: (),
        get_psets=lambda _: {},
    )
    return provider


def test_ifc_limit_never_returns_a_silently_truncated_index():
    assert len(ifc_adapter_rows(2).elements()) == 2
    with pytest.raises(DomainError, match="No partial index was published"):
        ifc_adapter_rows(3).elements()


def test_ifc_specific_selection_is_not_limited_by_unrelated_elements():
    assert [item.id for item in ifc_adapter_rows(3).elements(element_id="2")] == ["2"]


def test_ifc_overflow_cannot_change_active_source(services, admin, monkeypatch):
    from app.domain.errors import DomainError

    with services.factory.open() as repo:
        initial = repo.state("harbor-east")
    run = services.jobs.upload("harbor-east", "oversized.ifc", b"fixture", "bim_import", admin)
    monkeypatch.setattr(services.jobs.ifc, "parse", lambda _: ifc_adapter_rows(3).elements())
    with pytest.raises(DomainError):
        services.runtime.start(run.id)
    with services.factory.open() as repo:
        assert repo.bim_index("harbor-east") is None
        assert repo.state("harbor-east").version == initial.version
        assert repo.job(run.id).result is None
        assert repo.run(run.id).status == "FAILED"
