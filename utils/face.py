import os
import tempfile

from PIL import Image


def prepare_search_image(image_path: str) -> str:
    """Crop to face region if possible, otherwise return resized original."""
    try:
        import face_recognition
        image = face_recognition.load_image_file(image_path)
        locations = face_recognition.face_locations(image)
        if locations:
            top, right, bottom, left = locations[0]
            # Add margin around face
            h, w = image.shape[:2]
            margin = int((bottom - top) * 0.4)
            top = max(0, top - margin)
            left = max(0, left - margin)
            bottom = min(h, bottom + margin)
            right = min(w, right + margin)

            pil_img = Image.fromarray(image[top:bottom, left:right])
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=os.path.dirname(image_path))
            pil_img.save(tmp.name, "JPEG", quality=90)
            return tmp.name
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: just resize the original for consistency
    try:
        img = Image.open(image_path)
        img.thumbnail((800, 800))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=os.path.dirname(image_path))
        img.save(tmp.name, "JPEG", quality=90)
        return tmp.name
    except Exception:
        return image_path
