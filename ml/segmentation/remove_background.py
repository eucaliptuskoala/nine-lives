from ultralytics import YOLO
from PIL import Image
import numpy as np
import cv2
import torch

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = YOLO("yolo11s-seg.pt")
    return _model


def remove_background(image: Image.Image) -> Image.Image:
    model = _get_model()
    results = model(image, verbose=False)

    orig = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    h, w = orig.shape[:2]
    mask_union = np.zeros((h, w), dtype=np.uint8)

    for r in results:
        if r.masks is None:
            continue
        for cls, mask_xy in zip(r.boxes.cls, r.masks.xy):
            if int(cls) == 15:
                contour = mask_xy.astype(np.int32).reshape(-1, 1, 2)
                cv2.drawContours(mask_union, [contour], -1, 255, cv2.FILLED)

    image_rgba = image.convert("RGBA")
    r, g, b, a = image_rgba.split()
    mask_pil = Image.fromarray(mask_union, mode="L")
    return Image.merge("RGBA", (r, g, b, mask_pil))
