"""
Color Extractor — YOLO segmentation + scikit-learn KMeans.

Segments the cat out of the photo (removing the background) using YOLO
(`yolo11s-seg.pt`, COCO class 15 = cat), then runs KMeans over the cat's
non-transparent pixels to find the dominant fur colors and their relative
ratios.

Heavy dependencies (`ultralytics`, `cv2`, `numpy`, `scikit-learn`) are imported
lazily inside the functions that need them, so importing this module (and unit
testing the pure `_palette_from_labels` helper) never requires the ML extra to
be installed. Install the real pipeline deps with `uv sync --extra ml`.

Related: Requirements 3.1, 3.2, 3.3
"""

MODEL_NAME = "yolo11s-seg.pt"
COCO_CAT_CLASS = 15
MAX_RETRIES = 3

# Module-level singleton cache for the loaded YOLO segmentation model.
_yolo = None


def _get_yolo():
    """Lazily load and cache the YOLO segmentation model.

    Heavy import happens inside this function. Monkeypatch in tests to avoid
    loading real weights.
    """
    global _yolo
    if _yolo is None:
        from ultralytics import YOLO

        _yolo = YOLO(MODEL_NAME)
    return _yolo


def _remove_background(image):
    """Return the PIL image as RGBA with non-cat pixels made transparent.

    Mirrors ml/segmentation/remove_background.py: runs YOLO segmentation, builds
    a union mask of every detected cat (COCO class 15) instance via
    `cv2.drawContours`, and uses that mask as the alpha channel.
    """
    import cv2
    import numpy as np

    model = _get_yolo()
    results = model(image, verbose=False)

    orig = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    h, w = orig.shape[:2]
    mask_union = np.zeros((h, w), dtype=np.uint8)

    for r in results:
        if r.masks is None:
            continue
        for cls, mask_xy in zip(r.boxes.cls, r.masks.xy):
            if int(cls) == COCO_CAT_CLASS:
                contour = mask_xy.astype(np.int32).reshape(-1, 1, 2)
                cv2.drawContours(mask_union, [contour], -1, 255, cv2.FILLED)

    from PIL import Image

    image_rgba = image.convert("RGBA")
    red, green, blue, _alpha = image_rgba.split()
    mask_pil = Image.fromarray(mask_union, mode="L")
    return Image.merge("RGBA", (red, green, blue, mask_pil))


def _palette_from_labels(centroids, counts) -> list[dict]:
    """Convert KMeans centroids + per-cluster pixel counts into a color palette.

    Pure helper — dependency-light and deterministic. This is the key unit under
    test.

    Args:
        centroids: iterable of RGB triples (float or int channels, 0-255 range).
        counts: iterable of pixel counts per corresponding centroid (>= 0).

    Returns:
        A list of {"hex": "#RRGGBB", "ratio": float} dicts, one per centroid,
        where ratio = count / total (ratios sum to ~1.0). Each hex is uppercase
        with channels clamped to 0-255 and rounded to the nearest integer.
    """
    centroids = list(centroids)
    counts = [float(c) for c in counts]
    total = sum(counts)

    palette: list[dict] = []
    for centroid, count in zip(centroids, counts):
        channels = list(centroid)
        r, g, b = (channels[0], channels[1], channels[2])

        def _clamp(v: float) -> int:
            return max(0, min(255, int(round(v))))

        hex_code = "#{:02X}{:02X}{:02X}".format(_clamp(r), _clamp(g), _clamp(b))
        ratio = (count / total) if total > 0 else 0.0
        palette.append({"hex": hex_code, "ratio": ratio})

    return palette


def extract_colors(image_bytes: bytes, n_colors: int = 5) -> list[dict]:
    """Extract the dominant fur colors (with ratios) from a cat photo.

    Segments the cat via YOLO, selects the non-transparent (alpha > 0) RGB
    pixels, runs KMeans over them, and returns the palette with per-color
    ratios. Retries up to MAX_RETRIES times on failure before re-raising.
    """
    import io

    last_exc: Exception | None = None
    for _attempt in range(MAX_RETRIES):
        try:
            import numpy as np
            from PIL import Image
            from sklearn.cluster import KMeans

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            segmented = _remove_background(image)

            arr = np.array(segmented)  # (H, W, 4) RGBA
            alpha = arr[:, :, 3]
            rgb_pixels = arr[:, :, :3][alpha > 0]

            if len(rgb_pixels) == 0:
                # Nothing segmented — fall back to all pixels.
                rgb_pixels = np.array(image).reshape(-1, 3)

            # Gracefully handle fewer unique colors than requested clusters.
            unique_pixels = np.unique(rgb_pixels, axis=0)
            clusters = min(n_colors, len(unique_pixels))
            clusters = max(1, clusters)

            kmeans = KMeans(n_clusters=clusters, n_init=10, random_state=42)
            labels = kmeans.fit_predict(rgb_pixels)

            counts = np.bincount(labels, minlength=clusters)
            return _palette_from_labels(kmeans.cluster_centers_, counts)
        except Exception as exc:  # noqa: BLE001 — retry then re-raise
            last_exc = exc

    if last_exc is None:
        raise RuntimeError("Unexpected: no retry attempt made")
    raise last_exc
