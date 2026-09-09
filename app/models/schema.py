import json
from enum import Enum


class InvoiceStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    NEEDS_ATTENTION = "needs_attention"


STATUS_LABELS_VI = {
    InvoiceStatus.PENDING_REVIEW.value: "Mới",
    InvoiceStatus.CONFIRMED.value: "Đã xác nhận",
    InvoiceStatus.NEEDS_ATTENTION.value: "Cần rà soát",
}

REASON_LABELS_VI = {
    "ocr_response_unparseable": "OCR trả về dữ liệu không đọc được, cần nhập tay lại toàn bộ",
    "confidence_missing": "OCR không kèm độ tin cậy cho một số trường, đã ẩn giá trị để bạn kiểm tra",
    "ocr_low_confidence": "Một số trường có độ tin cậy thấp, đã ẩn giá trị để bạn kiểm tra",
    "ocr_provider_unavailable": "Không thể kết nối dịch vụ OCR (mạng/timeout/API lỗi), cần thử lại hoặc nhập tay",
    "ocr_no_fields_extracted": "OCR không đọc được trường nào trên hóa đơn này, cần kiểm tra/nhập tay",
}


def status_label(status: str) -> str:
    return STATUS_LABELS_VI.get(status, status)


def reason_label(reason_code: str) -> str:
    return REASON_LABELS_VI.get(reason_code, reason_code)


def parse_review_reasons(review_reasons_json: str | None) -> list[str]:
    if not review_reasons_json:
        return []
    try:
        return json.loads(review_reasons_json)
    except (json.JSONDecodeError, TypeError):
        return []


def invoice_needs_review(review_reasons_json: str | None) -> bool:
    return len(parse_review_reasons(review_reasons_json)) > 0


def format_number(value) -> str:
    """Dinh dang so kieu Viet de de doc/de kiem tra: nhom 3 chu so cach
    nhau 1 khoang trang (vd 7150000 -> '7 150 000'). Tra ve chuoi rong neu
    value la None (chua xac dinh), giu nguyen chuoi goc neu khong phai so.
    """
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        return f"{int(num):,}".replace(",", " ")
    text = f"{num:,.3f}".replace(",", " ")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
