"""Image processing helpers for uploaded content images."""

from __future__ import annotations

import io

from PIL import Image, ImageOps

_DEFAULT_MAX_DIMENSION = 1600
_MAX_IMAGE_PIXELS = 25_000_000
_JPEG_QUALITY = 82
_WEBP_QUALITY = 82
_RESIZABLE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageTooLargeError(ValueError):
    """The decoded image would exceed the upload processing memory budget."""


def optimize_image_bytes(content: bytes, *, max_dimension: int = _DEFAULT_MAX_DIMENSION) -> bytes:
    """Downscale and recompress an uploaded image for web delivery.

    Falls back to returning the original bytes untouched whenever the
    content can't be decoded as an image (e.g. animated GIFs, or any
    payload Pillow doesn't understand) so uploads never fail because of
    this optimization step.
    """

    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > _MAX_IMAGE_PIXELS:
                raise ImageTooLargeError("이미지는 2,500만 픽셀 이하만 허용합니다.")
            image_format = image.format
            if image_format not in _RESIZABLE_FORMATS:
                return content

            # JPEG draft decoding and thumbnailing avoid copying the full-resolution image.
            image.draft(image.mode, (max_dimension, max_dimension))
            if max(image.size) > max_dimension:
                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            image = ImageOps.exif_transpose(image)
            if image is None:
                return content

            buffer = io.BytesIO()
            if image_format == "JPEG":
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                image.save(
                    buffer,
                    format="JPEG",
                    quality=_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
            elif image_format == "WEBP":
                image.save(buffer, format="WEBP", quality=_WEBP_QUALITY, method=6)
            else:
                image.save(buffer, format="PNG", optimize=True)

            optimized = buffer.getvalue()
    except (ImageTooLargeError, Image.DecompressionBombError) as error:
        raise ImageTooLargeError("이미지는 2,500만 픽셀 이하만 허용합니다.") from error
    except Exception:
        return content

    return optimized if len(optimized) < len(content) else content
