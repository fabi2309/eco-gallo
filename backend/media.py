"""Decode and re-encode images, discarding metadata and appended payloads."""
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 20000000


def normalize_image(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('Formato de imagen no permitido.')
                image.load()
                image = ImageOps.exif_transpose(image)
                image.thumbnail((2400, 2400))
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                output = io.BytesIO()
                image.save(output, format='WEBP', quality=85)
                return output.getvalue(), 'webp'
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('La imagen está dañada, es demasiado grande o no es compatible.') from None
