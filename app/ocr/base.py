from abc import ABC, abstractmethod
from pathlib import Path


class OcrAdapter(ABC):
    """Interface chung cho moi nha cung cap OCR (mock, groq, ...).

    extract() KHONG duoc phep raise loi ra ngoai vi bat ky ly do gi (mang,
    timeout, API, JSON hong...) - moi loi phai duoc bat va tra ve ket qua
    hop le dang unified schema (xem app/models/ocr_schema.py) voi cac field
    None + review_reasons phu hop, de tang goi (upload router) khong bao gio
    bi crash vi loi tu OCR provider.
    """

    provider_name: str = "unknown"

    @abstractmethod
    def extract(self, image_path: Path) -> dict:
        raise NotImplementedError
