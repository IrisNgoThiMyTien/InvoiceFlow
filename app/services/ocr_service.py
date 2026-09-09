"""Dieu phoi OCR: goi adapter -> kiem tra/chuan hoa JSON -> luu vao invoice.

Ham run_ocr_for_invoice() la diem duy nhat noi upload router goi den, va no
KHONG bao gio de loi thoat ra ngoai - moi that bai (mang, timeout, API,
JSON hong, hoac loi khong luong truoc nao khac) deu duoc bat va ket qua
"can ra soat" duoc luu lai, de ung dung khong bao gio dung dot ngot.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings
from app.models.ocr_schema import REASON_OCR_PROVIDER_UNAVAILABLE, empty_result, validate_and_normalize
from app.ocr.base import OcrAdapter
from app.ocr.factory import get_ocr_adapter
from app.services import invoice_service

logger = logging.getLogger(__name__)


def run_ocr_for_invoice(invoice_id: int, image_path: Path) -> None:
    adapter = get_ocr_adapter()

    try:
        raw_result = adapter.extract(image_path)
    except Exception:
        # Phong ho them: du adapter da duoc yeu cau khong raise, van bat o
        # day de dam bao tuyet doi khong lam sap request upload.
        logger.exception(
            "Adapter OCR '%s' raise loi ngoai du kien khi xu ly invoice #%s",
            getattr(adapter, "provider_name", "unknown"),
            invoice_id,
        )
        raw_result = empty_result([REASON_OCR_PROVIDER_UNAVAILABLE])

    # Kiem tra JSON truoc khi luu: chuan hoa lai theo unified schema, ep
    # null cho moi truong thieu confidence / confidence thap, du adapter co
    # loi hay khong.
    normalized = validate_and_normalize(raw_result, settings.ocr_confidence_threshold)

    try:
        invoice_service.update_ocr_result(
            invoice_id=invoice_id,
            ocr_provider=_provider_name(adapter),
            ocr_raw_json=json.dumps(raw_result, ensure_ascii=False),
            normalized=normalized,
        )
    except Exception:
        logger.exception("Khong the luu ket qua OCR cho invoice #%s", invoice_id)


def _provider_name(adapter: OcrAdapter) -> str:
    return getattr(adapter, "provider_name", "unknown")
