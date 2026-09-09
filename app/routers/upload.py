import logging

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.config import settings
from app.services import invoice_service, ocr_service
from app.services.storage_service import InvalidUploadError, save_uploaded_image
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/upload")
def upload_form(request: Request):
    return templates.TemplateResponse(request, "upload.html", {"error": None})


@router.post("/upload")
async def upload_submit(request: Request, file: UploadFile):
    try:
        stored_filename, original_filename = save_uploaded_image(file)
    except InvalidUploadError as exc:
        return templates.TemplateResponse(
            request, "upload.html", {"error": str(exc)}, status_code=400
        )
    except Exception:
        logger.exception("Loi khong mong doi khi xu ly file upload")
        return templates.TemplateResponse(
            request,
            "upload.html",
            {"error": "Có lỗi không mong muốn khi xử lý file. Vui lòng thử lại."},
            status_code=500,
        )

    try:
        invoice_id = invoice_service.create_pending_invoice(stored_filename, original_filename)
    except Exception:
        logger.exception("Loi khi tao ban ghi hoa don trong CSDL")
        return templates.TemplateResponse(
            request,
            "upload.html",
            {"error": "Đã lưu ảnh nhưng không thể tạo bản ghi hóa đơn. Vui lòng thử lại."},
            status_code=500,
        )

    # Chay OCR (Demo hoac Real tuy cau hinh) ngay sau khi tao ban ghi.
    # ocr_service.run_ocr_for_invoice() da tu bat moi loi ben trong (mang,
    # timeout, API, JSON hong...) nen o day khong the lam hong redirect,
    # nhung van boc try/except them 1 lop de tuyet doi khong lam sap request.
    try:
        image_path = settings.upload_dir_path / stored_filename
        ocr_service.run_ocr_for_invoice(invoice_id, image_path)
    except Exception:
        logger.exception("Loi ngoai du kien khi chay OCR cho invoice #%s", invoice_id)

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)
