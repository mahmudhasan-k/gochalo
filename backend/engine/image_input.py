"""Bounded, in-memory screenshot validation. No uploads to a files API."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from ai_service import AnalysisError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_SIDE = 6000


def prepare_image(data: bytes, filename: str) -> tuple[bytes, str]:
    """Check actual decoded content and strip metadata before extraction."""
    suffix = filename.rsplit(".", 1)[-1].lower()
    expected = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}.get(suffix)
    if expected is None:
        raise AnalysisError("image_invalid", "Only PNG and JPEG images are accepted")
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise AnalysisError("image_size", "Image exceeds the upload limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != expected or getattr(image, "n_frames", 1) != 1:
                    raise AnalysisError("image_invalid", "A single PNG or JPEG image is required")
                if image.width * image.height > MAX_IMAGE_PIXELS or max(image.size) > MAX_IMAGE_SIDE:
                    raise AnalysisError("image_dimensions", "Image dimensions exceed the limit")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                clean = ImageOps.exif_transpose(image).convert("RGBA" if expected == "PNG" else "RGB")
                clean.info.clear()
                output = BytesIO()
                clean.save(output, format=expected)
                prepared = output.getvalue()
        if len(prepared) > MAX_IMAGE_BYTES:
            raise AnalysisError("image_size", "Image exceeds the upload limit")
        return prepared, "image/png" if expected == "PNG" else "image/jpeg"
    except AnalysisError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AnalysisError("image_dimensions", "Image dimensions exceed the limit") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise AnalysisError("image_invalid", "Image could not be read") from None
