import io

from app.domain.errors import CapabilityUnavailable, DomainError


def clean_image(content: bytes) -> bytes:
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise CapabilityUnavailable(
            "Install Pillow with the models extra for safe image decoding"
        ) from exc
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise DomainError("Vision source must actually decode as PNG, JPEG, or WebP")
            if source.width * source.height > 20_000_000:
                raise DomainError("Image exceeds safe pixel limit")
            source.load()
            clean = ImageOps.exif_transpose(source).convert("RGB")
            clean.thumbnail((1600, 1600))
            target = io.BytesIO()
            # New RGB image plus empty metadata prevents EXIF/ICC/location forwarding.
            image = Image.new("RGB", clean.size)
            image.paste(clean)
            image.save(target, format="PNG")
            return target.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DomainError("Invalid or unsafe image") from exc
