import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


class InvalidUploadError(Exception):
    """Loi do nguoi dung: file upload khong hop le (sai dinh dang/qua lon/hong)."""


def save_uploaded_image(file: UploadFile) -> tuple[str, str]:
    """Kiem tra va luu an toan 1 file anh upload vao thu muc uploads/.

    Tra ve (stored_filename, original_filename). Ten file goc KHONG bao gio
    duoc dung de tao duong dan tren dia - luon sinh ten moi bang UUID de
    tranh path traversal / ghi de file.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidUploadError(
            f"Loại file '{file.content_type or 'không rõ'}' không được hỗ trợ. "
            "Chỉ chấp nhận ảnh JPG hoặc PNG."
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidUploadError(
            f"Đuôi file '{ext or '(không rõ)'}' không được hỗ trợ. Chỉ chấp nhận .jpg, .jpeg hoặc .png."
        )

    raw_bytes = file.file.read()
    if not raw_bytes:
        raise InvalidUploadError("File tải lên trống, vui lòng chọn lại ảnh hóa đơn.")

    max_bytes = settings.max_upload_size_bytes
    if len(raw_bytes) > max_bytes:
        size_mb = len(raw_bytes) / 1024 / 1024
        raise InvalidUploadError(
            f"File quá lớn ({size_mb:.1f} MB). Giới hạn tối đa {settings.max_upload_size_mb} MB."
        )

    _verify_is_real_image(raw_bytes)

    settings.upload_dir_path.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = settings.upload_dir_path / stored_filename
    try:
        with dest_path.open("wb") as out:
            out.write(raw_bytes)
    except OSError as exc:
        raise InvalidUploadError(
            "Không thể lưu file vào máy chủ. Vui lòng thử lại hoặc liên hệ quản trị viên."
        ) from exc

    # Chi lay ten file, bo moi thanh phan thu muc, de hien thi an toan.
    original_filename = Path(file.filename or "hoa_don").name
    return stored_filename, original_filename


def _verify_is_real_image(raw_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidUploadError(
            "File không phải là ảnh hợp lệ (có thể bị hỏng hoặc không đúng định dạng JPG/PNG)."
        ) from exc
