from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple
import re

import numpy as np
from PIL import Image, ImageOps
from paddleocr import PaddleOCR

from validation.thai_id import find_thai_citizen_id


@dataclass
class OCRLine:
    text: str
    score: float
    box: list
    model: str


@dataclass
class OCRResult:
    lines: List[OCRLine]
    detected_language: str
    mean_confidence: float

    @property
    def texts(self) -> List[str]:
        return [x.text for x in self.lines if x.text]


@lru_cache(maxsize=4)
def _build_model(model_key: str) -> PaddleOCR:
    common = dict(
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
        cpu_threads=4,
        enable_mkldnn=False,
    )
    if model_key == "thai":
        return PaddleOCR(text_recognition_model_name="th_PP-OCRv5_mobile_rec", **common)
    return PaddleOCR(**common)


def _extract_lines(raw_results, model_name: str) -> List[OCRLine]:
    lines: List[OCRLine] = []
    for result in raw_results:
        payload = getattr(result, "json", None)
        if callable(payload):
            payload = payload()
        if not isinstance(payload, dict):
            continue
        data = payload.get("res", payload)
        texts = data.get("rec_texts", []) or []
        scores = data.get("rec_scores", []) or []
        boxes = data.get("rec_boxes", []) or data.get("rec_polys", []) or []
        for idx, text in enumerate(texts):
            text = str(text).strip()
            if not text:
                continue
            try:
                score = float(scores[idx])
            except Exception:
                score = 0.0
            try:
                box = np.asarray(boxes[idx]).tolist()
            except Exception:
                box = []
            lines.append(OCRLine(text=text, score=score, box=box, model=model_name))
    return lines


def _mean_conf(lines: Iterable[OCRLine]) -> float:
    vals = [x.score for x in lines if x.text]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _script_counts(text: str) -> Dict[str, int]:
    counts = {"th": 0, "zh": 0, "ja": 0, "ko": 0, "ar": 0, "cy": 0, "latin": 0}
    for ch in text:
        cp = ord(ch)
        if 0x0E00 <= cp <= 0x0E7F:
            counts["th"] += 1
        elif 0x3040 <= cp <= 0x30FF:
            counts["ja"] += 1
        elif 0xAC00 <= cp <= 0xD7AF:
            counts["ko"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            counts["zh"] += 1
        elif 0x0600 <= cp <= 0x06FF:
            counts["ar"] += 1
        elif 0x0400 <= cp <= 0x04FF:
            counts["cy"] += 1
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            counts["latin"] += 1
    return counts


def detect_language(lines: Iterable[OCRLine]) -> str:
    text = " ".join(x.text for x in lines)
    counts = _script_counts(text)
    labels = []
    if counts["th"] >= 3:
        labels.append("Thai")
    if counts["ja"] >= 2:
        labels.append("Japanese")
    elif counts["zh"] >= 2:
        labels.append("Chinese")
    if counts["ko"] >= 2:
        labels.append("Korean")
    if counts["ar"] >= 2:
        labels.append("Arabic")
    if counts["cy"] >= 2:
        labels.append("Cyrillic")
    if counts["latin"] >= 4:
        labels.append("Latin/English")
    return "+".join(labels) if labels else "Unknown"


def _dedupe(lines: List[OCRLine]) -> List[OCRLine]:
    chosen: Dict[str, OCRLine] = {}
    order: List[str] = []
    for line in lines:
        key = re.sub(r"\s+", "", line.text).casefold()
        if not key:
            continue
        if key not in chosen:
            chosen[key] = line
            order.append(key)
        elif line.score > chosen[key].score:
            chosen[key] = line
    return [chosen[k] for k in order]


def _box_rect(box: list) -> Optional[Tuple[float, float, float, float]]:
    try:
        arr = np.asarray(box, dtype=float)
    except Exception:
        return None
    if arr.ndim == 1 and arr.size >= 4:
        x1, y1, x2, y2 = arr[:4]
        return float(x1), float(y1), float(x2), float(y2)
    if arr.ndim >= 2 and arr.shape[-1] >= 2:
        xs = arr[..., 0].ravel()
        ys = arr[..., 1].ravel()
        return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
    return None


def _thai_id_retry_crop(image: Image.Image, lines: List[OCRLine]) -> Image.Image:
    width, height = image.size
    anchor = None
    for line in lines:
        compact = re.sub(r"[^a-z]", "", line.text.lower())
        if "identification" in compact or "identificat" in compact or "dentification" in compact:
            anchor = _box_rect(line.box)
            if anchor:
                break

    if anchor:
        _, y1, _, y2 = anchor
        line_h = max(12.0, y2 - y1)
        top = max(0, int(y1 - line_h * 3.0))
        bottom = min(height, int(y2 + line_h * 2.0))
    else:
        # Citizen number is normally in the upper part of a Thai ID card.
        top = 0
        bottom = max(1, int(height * 0.42))

    return image.crop((0, top, width, bottom))


def retry_thai_id_number(image: Image.Image, lines: List[OCRLine]) -> List[OCRLine]:
    """Retry only the Thai ID number area after checksum failure.

    This is intentionally conditional so normal PASS documents do not pay the extra OCR cost.
    """
    crop = _thai_id_retry_crop(image, lines)
    gray = ImageOps.grayscale(crop)
    gray = ImageOps.autocontrast(gray)
    scale = 3
    large = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)

    variants = [large.convert("RGB")]
    thresholded = large.point(lambda p: 255 if p > 155 else 0).convert("RGB")
    variants.append(thresholded)

    all_retry: List[OCRLine] = []
    for idx, variant in enumerate(variants, start=1):
        retry = _extract_lines(
            _build_model("general").predict(np.array(variant)),
            f"thai_id_retry_{idx}",
        )
        all_retry.extend(retry)
        if find_thai_citizen_id([x.text for x in retry]):
            break
    return _dedupe(all_retry)


def run_auto_ocr(image: Image.Image, include_thai_candidate: bool = True) -> OCRResult:
    arr = np.array(image)
    general = _extract_lines(_build_model("general").predict(arr), "general")
    merged = list(general)

    if include_thai_candidate:
        thai = _extract_lines(_build_model("thai").predict(arr), "thai")
        thai_chars = _script_counts(" ".join(x.text for x in thai))["th"]
        if thai_chars >= 3 or _mean_conf(thai) > _mean_conf(general) + 0.12:
            merged.extend(thai)

    merged = _dedupe(merged)
    return OCRResult(
        lines=merged,
        detected_language=detect_language(merged),
        mean_confidence=_mean_conf(merged),
    )
