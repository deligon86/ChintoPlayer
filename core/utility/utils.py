from PIL import Image
from io import BytesIO
import os


def load_default_image(target_size=(600, 600), downsample=False, image_path="assets/default.png"):
    """
    Load the default image from path
    :param target_size:
    :param downsample:
    :param image_path:
    :return:
    """
    working_env = os.environ.get('WORKING_DIR')
    path = os.path.join(working_env, image_path)
    image = Image.open(path)

    if image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')

    if not downsample:
        out_buffer = BytesIO()
        image.save(out_buffer, format="JPEG", quality=85, optimize=True)
        return out_buffer.getvalue()

    image.thumbnail(target_size, Image.Resampling.LANCZOS)
    out_buffer = BytesIO()
    image.save(out_buffer, format="JPEG", quality=85, optimize=True)
    return out_buffer.getvalue()
