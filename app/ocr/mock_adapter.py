import json
from pathlib import Path

from app.ocr.base import OcrAdapter

_FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mock_ocr_response.json"


def get_demo_invoice_json() -> dict:
    """Doc du lieu hoa don mau co dinh tu fixture (Demo mode).

    Khong goi bat ky API OCR ngoai nao.
    """
    with _FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class MockOcrAdapter(OcrAdapter):
    """Demo mode: tra ve du lieu OCR mau tinh, khong goi mang."""

    provider_name = "mock"

    def extract(self, image_path: Path) -> dict:
        return get_demo_invoice_json()
