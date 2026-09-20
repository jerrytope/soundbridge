"""Image processing for profile photos and release artwork.

Pillow replaces sharp. The pipeline matches server/backend.js exactly so stored
images look the same as before: honour EXIF rotation, fit inside 640x640
without enlarging, flatten transparency onto the interface background
(#1a1b1e), encode JPEG at quality 80.
"""
import base64
import io
import re

from django.conf import settings
from PIL import Image, ImageOps

DATA_URL = re.compile(r'^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/]+=*$')
BACKGROUND = (0x1A, 0x1B, 0x1E)
MAX_EDGE = 640
QUALITY = 80
MAX_PIXELS = 40_000_000


class ImageError(ValueError):
    """Raised with the message the UI shows the creator."""


def decode_data_url(value):
    if not isinstance(value, str) or not DATA_URL.match(value):
        raise ImageError('Choose a JPG, PNG or WebP image.')
    try:
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
    except Exception:
        raise ImageError('Choose a JPG, PNG or WebP image.')
    if len(raw) > settings.IMAGE_MAX_BYTES:
        raise ImageError('Choose an image smaller than 5 MB.')
    return raw


def process(raw):
    """Return JPEG bytes for the supplied image data."""
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.verify()
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ImageError('The image is invalid or too large.')
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGBA')
                flattened = Image.new('RGB', image.size, BACKGROUND)
                flattened.paste(image, mask=image.split()[-1])
                image = flattened
            else:
                image = image.convert('RGB')
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=QUALITY, optimize=True)
            return buffer.getvalue()
    except ImageError:
        raise
    except Exception:
        raise ImageError('The image is invalid or too large.')


def store(user, data_url):
    """Decode, resize and store an image for this account."""
    from accounts.models import StoredImage

    encoded = process(decode_data_url(data_url))
    used = sum(image.byte_size for image in StoredImage.objects.filter(user=user))
    if used + len(encoded) > settings.IMAGE_STORAGE_PER_ACCOUNT:
        raise ImageError('Image storage is full for this account.')
    image = StoredImage.objects.create(user=user, bytes=encoded, byte_size=len(encoded))
    return image


def store_upload(user, uploaded_file):
    """Store an image chosen with a plain file input (the template path)."""
    if uploaded_file.size > settings.IMAGE_MAX_BYTES:
        raise ImageError('Choose an image smaller than 5 MB.')
    if uploaded_file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise ImageError('Choose a JPG, PNG or WebP image.')
    from accounts.models import StoredImage

    encoded = process(uploaded_file.read())
    used = sum(image.byte_size for image in StoredImage.objects.filter(user=user))
    if used + len(encoded) > settings.IMAGE_STORAGE_PER_ACCOUNT:
        raise ImageError('Image storage is full for this account.')
    return StoredImage.objects.create(user=user, bytes=encoded, byte_size=len(encoded))
