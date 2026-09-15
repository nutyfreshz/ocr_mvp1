from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List

import cv2
import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageSequence


def load_pages(file_bytes: bytes, filename: str, max_pages: int = 30) -> List[Image.Image]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for idx, page in enumerate(doc):
            if idx >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(img)
        doc.close()
        return pages

    img = Image.open(BytesIO(file_bytes))
    if suffix in {".tif", ".tiff"}:
        pages = []
        for idx, frame in enumerate(ImageSequence.Iterator(img)):
            if idx >= max_pages:
                break
            pages.append(ImageOps.exif_transpose(frame.copy()).convert("RGB"))
        return pages
    return [ImageOps.exif_transpose(img).convert("RGB")]


def _deskew(pil_image: Image.Image) -> Image.Image:
    arr = np.array(pil_image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    min_len = max(80, int(min(gray.shape) * 0.25))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=min_len, maxLineGap=20)
    if lines is None:
        return pil_image
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -8 <= angle <= 8:
            angles.append(angle)
    if len(angles) < 3:
        return pil_image
    angle = float(np.median(angles))
    if abs(angle) < 0.35:
        return pil_image
    h, w = arr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(arr, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(rotated)


def normalize_image(image: Image.Image, max_side: int = 2200) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    image = _deskew(image)
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Sharpness(image).enhance(1.15)
    return image
