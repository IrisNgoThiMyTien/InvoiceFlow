"""Unified OCR JSON schema dung chung cho moi adapter (mock, groq, ...).

Nguyen tac bat buoc: KHONG bao gio tu doan gia tri. Neu adapter khong chac
chan (thieu confidence, confidence qua thap, hoac khong doc duoc), field do
phai bi ep ve None va mot ma review_reason co dinh duoc them vao.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError, model_validator

# Ma ly do can ra soat (co dinh, khong phai text tu do)
REASON_OCR_RESPONSE_UNPARSEABLE = "ocr_response_unparseable"
REASON_CONFIDENCE_MISSING = "confidence_missing"
REASON_OCR_LOW_CONFIDENCE = "ocr_low_confidence"
REASON_OCR_PROVIDER_UNAVAILABLE = "ocr_provider_unavailable"
REASON_NO_FIELDS_EXTRACTED = "ocr_no_fields_extracted"

HEADER_FIELDS = [
    "invoice_type_name",
    "invoice_form_number",
    "invoice_number",
    "invoice_date",
    "seller_name",
    "seller_tax_code",
    "buyer_name",
    "buyer_tax_code",
    "buyer_company_name",
    "buyer_address",
    "buyer_bank_account",
    "buyer_payment_method",
    "subtotal",
    "tax_amount",
    "total_amount",
    "currency",
]


class FieldValue(BaseModel):
    value: str | float | None = None
    confidence: float | None = None


class LineItemValue(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None
    confidence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_key_synonyms(cls, data):
        """Chap nhan mot so ten khoa tuong duong ma LLM hay dung thay the
        (vd 'total_price' thay vi 'line_total') - day KHONG phai doan gia
        tri, chi la dung sai ten truong JSON cho cung 1 y nghia."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if data.get("line_total") is None and data.get("total_price") is not None:
            data["line_total"] = data["total_price"]
        return data


class InvoiceOcrResult(BaseModel):
    invoice_type_name: FieldValue = Field(default_factory=FieldValue)
    invoice_form_number: FieldValue = Field(default_factory=FieldValue)
    invoice_number: FieldValue = Field(default_factory=FieldValue)
    invoice_date: FieldValue = Field(default_factory=FieldValue)
    seller_name: FieldValue = Field(default_factory=FieldValue)
    seller_tax_code: FieldValue = Field(default_factory=FieldValue)
    buyer_name: FieldValue = Field(default_factory=FieldValue)
    buyer_tax_code: FieldValue = Field(default_factory=FieldValue)
    buyer_company_name: FieldValue = Field(default_factory=FieldValue)
    buyer_address: FieldValue = Field(default_factory=FieldValue)
    buyer_bank_account: FieldValue = Field(default_factory=FieldValue)
    buyer_payment_method: FieldValue = Field(default_factory=FieldValue)
    subtotal: FieldValue = Field(default_factory=FieldValue)
    tax_amount: FieldValue = Field(default_factory=FieldValue)
    total_amount: FieldValue = Field(default_factory=FieldValue)
    currency: FieldValue = Field(default_factory=FieldValue)
    line_items: list[LineItemValue] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


def empty_result(reasons: list[str]) -> dict:
    """Ket qua rong an toan: moi field None, kem ly do can ra soat."""
    result = InvoiceOcrResult(review_reasons=list(reasons))
    return result.model_dump()


def validate_and_normalize(raw: dict, confidence_threshold: float) -> dict:
    """Kiem tra JSON tho tu adapter truoc khi luu.

    - Neu raw khong dung cau truc schema -> tra ve empty_result() kem
      REASON_OCR_RESPONSE_UNPARSEABLE (khong raise, luon tra ve du lieu dung
      hinh dang de noi goi luu duoc an toan).
    - Voi tung field header: neu co value nhung thieu/confidence khong hop
      le -> ep value=None + REASON_CONFIDENCE_MISSING.
      Neu confidence duoi nguong -> ep value=None + REASON_OCR_LOW_CONFIDENCE.
    """
    try:
        parsed = InvoiceOcrResult.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return empty_result([REASON_OCR_RESPONSE_UNPARSEABLE])

    reasons = list(dict.fromkeys(parsed.review_reasons))  # giu thu tu, bo trung

    for name in HEADER_FIELDS:
        field: FieldValue = getattr(parsed, name)
        if field.value is None:
            continue
        if field.confidence is None:
            field.value = None
            _add_reason(reasons, REASON_CONFIDENCE_MISSING)
        elif field.confidence < confidence_threshold:
            field.value = None
            _add_reason(reasons, REASON_OCR_LOW_CONFIDENCE)

    all_header_empty = all(getattr(parsed, name).value is None for name in HEADER_FIELDS)
    if all_header_empty and not parsed.line_items and not reasons:
        # Schema hop le nhung khong co truong nao doc duoc va cung khong co
        # ly do nao khac - van phai danh dau can ra soat, tranh de hoa don
        # trong "sach se" gay hieu lam la da OCR thanh cong.
        _add_reason(reasons, REASON_NO_FIELDS_EXTRACTED)

    parsed.review_reasons = reasons
    return parsed.model_dump()


def _add_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)
