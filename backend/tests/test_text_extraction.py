from __future__ import annotations

import base64
import unittest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.text_extraction import extract_text_preview


class TextExtractionTests(unittest.TestCase):
    def test_extract_pdf_text(self) -> None:
        pdf_base64 = (
            "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5k"
            "b2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPj4KZW5kb2Jq"
            "CjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCAyMDAgMjAw"
            "XQovQ29udGVudHMgNCAwIFIKL1Jlc291cmNlcyA8PAovRm9udCA8PAovRjEgNSAwIFIKPj4KPj4KPj4K"
            "ZW5kb2JqCjQgMCBvYmoKPDwKL0xlbmd0aCA0NAo+PnN0cmVhbQpCVAovRjEgMjQgVGYKNTAgMTUwIFRk"
            "CihIZWxsbyBQREYpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKNSAwIG9iago8PAovVHlwZSAvRm9udAov"
            "U3VidHlwZSAvVHlwZTEKL0Jhc2VGb250IC9IZWx2ZXRpY2EKPj4KZW5kb2JqCnhyZWYKMCA2CjAwMDAw"
            "MDAwMCA2NTUzNSBmIAowMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDcxIDAwMDAwIG4gCjAwMDAwMDE2"
            "NCAwMDAwMCBuIAowMDAwMDAyNTUgMDAwMDAgbiAKMDAwMDAwMzU4IDAwMDAwIG4gCnRyYWlsZXIKPDwK"
            "L1Jvb3QgMSAwIFIKL1NpemUgNgovSW5mbyA3IDAgUgo+PgpzdGFydHhyZWYKNDc2CiUlRU9G"
        )
        pdf_bytes = base64.b64decode(pdf_base64)
        preview = extract_text_preview(
            filename="sample.pdf",
            raw=pdf_bytes,
            content_type="application/pdf",
            max_chars=2000,
        )
        self.assertIn("Hello PDF", preview.body)

    def test_extract_html_text(self) -> None:
        html_bytes = "<html><body><h1>제목</h1><p>본문 내용입니다.</p></body></html>".encode("utf-8")
        preview = extract_text_preview(
            filename="sample.html",
            raw=html_bytes,
            content_type="text/html",
            max_chars=500,
        )
        self.assertIn("제목", preview.body)
        self.assertIn("본문 내용입니다.", preview.body)

    def test_extract_image_fallback(self) -> None:
        image_bytes = b"\xff\xd8\xff"  # JPEG header bytes
        preview = extract_text_preview(
            filename="image.jpg",
            raw=image_bytes,
            content_type="image/jpeg",
            max_chars=500,
        )
        self.assertIn("이미지에서 텍스트를 추출할 수 없습니다", preview.body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
