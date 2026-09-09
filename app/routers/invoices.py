import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import FormData

from app.config import settings
from app.models.schema import (
    format_number,
    invoice_needs_review,
    parse_review_reasons,
    reason_label,
    status_label,
)
from app.services import invoice_service, ocr_service
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

# (ten cot, nhan tieng Viet, la truong so tien/so luong hay khong)
# Truong "is_money=True" duoc hien thi da dinh dang nhom 3 chu so (vd
# "7 150 000") va parse lai khi luu - xem _to_float().
FIELD_DISPLAY = [
    ("invoice_type_name", "Tên loại hóa đơn", False),
    ("invoice_form_number", "Mẫu số", False),
    ("invoice_number", "Số hóa đơn", False),
    ("invoice_date", "Ngày hóa đơn (YYYY-MM-DD)", False),
    ("seller_name", "Người bán", False),
    ("seller_tax_code", "MST người bán", False),
    ("buyer_name", "Người mua", False),
    ("buyer_tax_code", "MST người mua", False),
    ("buyer_company_name", "Tên đơn vị", False),
    ("buyer_address", "Địa chỉ", False),
    ("buyer_bank_account", "Số tài khoản", False),
    ("buyer_payment_method", "Hình thức thanh toán", False),
    ("subtotal", "Tạm tính", True),
    ("tax_amount", "Thuế", True),
    ("total_amount", "Tổng tiền", True),
    ("currency", "Tiền tệ", False),
]


@router.get("/invoices")
def list_invoices(request: Request):
    try:
        invoices = invoice_service.list_invoices()
    except Exception:
        logger.exception("Loi khi tai danh sach hoa don")
        invoices = []
        error = "Không thể tải danh sách hóa đơn lúc này. Vui lòng thử lại sau."
        return templates.TemplateResponse(
            request,
            "invoice_list.html",
            {
                "invoices": invoices,
                "status_label": status_label,
                "needs_review": invoice_needs_review,
                "error": error,
            },
            status_code=500,
        )
    return templates.TemplateResponse(
        request,
        "invoice_list.html",
        {
            "invoices": invoices,
            "status_label": status_label,
            "needs_review": invoice_needs_review,
            "error": None,
        },
    )


def _detail_context(invoice, save_error: str | None = None) -> dict:
    line_items = invoice_service.list_line_items(invoice["id"])
    reasons = parse_review_reasons(invoice["review_reasons"])
    return {
        "invoice": invoice,
        "line_items": line_items,
        "status_label": status_label(invoice["status"]),
        "review_reasons": reasons,
        "review_reason_labels": [reason_label(r) for r in reasons],
        "needs_review": len(reasons) > 0,
        "header_fields": FIELD_DISPLAY,
        "missing_fields": {name for name, _, _ in FIELD_DISPLAY if invoice[name] is None},
        "format_number": format_number,
        "save_error": save_error,
    }


@router.get("/invoices/{invoice_id}")
def invoice_detail(request: Request, invoice_id: int):
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")

    return templates.TemplateResponse(request, "invoice_detail.html", _detail_context(invoice))


@router.post("/invoices/{invoice_id}/retry-ocr")
def retry_ocr(invoice_id: int):
    """Chay lai OCR tren chinh anh da luu (khong can nguoi dung upload lai).

    Dung cho truong hop lan chay truoc bi loi tam thoi (mang/timeout/API).
    Anh da nam san trong uploads/ tu luc nguoi dung tu chon qua nut Upload -
    o day chi doc lai file da co san trong he thong, khong dung toi bat ky
    duong dan file mau nao ben ngoai.
    """
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")

    try:
        image_path = settings.upload_dir_path / invoice["stored_filename"]
        ocr_service.run_ocr_for_invoice(invoice_id, image_path)
    except Exception:
        logger.exception("Loi ngoai du kien khi chay lai OCR cho invoice #%s", invoice_id)

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/save")
async def save_invoice(request: Request, invoice_id: int):
    """Luu du lieu nguoi dung da nhap/sua tay (bao gom cac truong OCR bo
    trong) va danh dau hoa don la 'confirmed'.
    """
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")

    try:
        form = await request.form()
        header = _parse_header_form(form)
        line_items = _parse_line_items_form(form)
        invoice_service.save_reviewed_invoice(invoice_id, header, line_items)
    except Exception:
        logger.exception("Loi khi luu chinh sua cho invoice #%s", invoice_id)
        refreshed = invoice_service.get_invoice(invoice_id) or invoice
        return templates.TemplateResponse(
            request,
            "invoice_detail.html",
            _detail_context(refreshed, save_error="Không thể lưu chỉnh sửa lúc này. Vui lòng thử lại."),
            status_code=500,
        )

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


def _parse_header_form(form: FormData) -> dict:
    def text(name: str):
        value = (form.get(name) or "").strip()
        return value or None

    def number(name: str):
        return _to_float(form.get(name))

    return {
        "invoice_type_name": text("invoice_type_name"),
        "invoice_form_number": text("invoice_form_number"),
        "invoice_number": text("invoice_number"),
        "invoice_date": text("invoice_date"),
        "seller_name": text("seller_name"),
        "seller_tax_code": text("seller_tax_code"),
        "buyer_name": text("buyer_name"),
        "buyer_tax_code": text("buyer_tax_code"),
        "buyer_company_name": text("buyer_company_name"),
        "buyer_address": text("buyer_address"),
        "buyer_bank_account": text("buyer_bank_account"),
        "buyer_payment_method": text("buyer_payment_method"),
        "subtotal": number("subtotal"),
        "tax_amount": number("tax_amount"),
        "total_amount": number("total_amount"),
        "currency": text("currency") or "VND",
    }


def _parse_line_items_form(form: FormData) -> list[dict]:
    descriptions = form.getlist("line_description")
    quantities = form.getlist("line_quantity")
    unit_prices = form.getlist("line_unit_price")
    line_totals = form.getlist("line_total")

    items = []
    for desc, qty, unit_price, total in zip(descriptions, quantities, unit_prices, line_totals):
        desc_clean = (desc or "").strip()
        qty_val = _to_float(qty)
        unit_price_val = _to_float(unit_price)
        total_val = _to_float(total)
        if not desc_clean and qty_val is None and unit_price_val is None and total_val is None:
            continue  # bo qua dong hoan toan trong (vd dong mau con sot lai)
        items.append(
            {
                "description": desc_clean or None,
                "quantity": qty_val,
                "unit_price": unit_price_val,
                "line_total": total_val,
            }
        )
    return items


def _to_float(raw) -> float | None:
    """Chuyen chuoi nguoi dung nhap thanh so, chap nhan dinh dang da nhom 3
    chu so bang khoang trang kieu bat ky (vd '7 150 000') hoac dau phay
    (vd '7,150,000')."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    no_whitespace = "".join(value.split())
    cleaned = no_whitespace.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None
