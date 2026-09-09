import logging

from app.config import settings
from app.ocr.base import OcrAdapter
from app.ocr.mock_adapter import MockOcrAdapter

logger = logging.getLogger(__name__)


def get_ocr_adapter() -> OcrAdapter:
    """Chon adapter OCR theo cau hinh OCR_PROVIDER.

    Neu OCR_PROVIDER=groq nhung thieu GROQ_API_KEY, tu dong roi ve Demo mode
    (mock) thay vi bao loi/dung ung dung - dung theo yeu cau "giu Demo mode
    khi khong co API key".
    """
    provider = (settings.ocr_provider or "mock").strip().lower()

    if provider == "groq":
        if not settings.groq_api_key:
            logger.warning(
                "OCR_PROVIDER=groq nhung thieu GROQ_API_KEY trong .env - "
                "tu dong dung Demo mode (mock) thay the."
            )
            return MockOcrAdapter()

        from app.ocr.groq_adapter import GroqOcrAdapter

        return GroqOcrAdapter(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            timeout_seconds=settings.ocr_timeout_seconds,
            max_retries=settings.ocr_max_retries,
        )

    return MockOcrAdapter()
