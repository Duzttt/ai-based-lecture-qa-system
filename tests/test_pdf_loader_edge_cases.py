import pytest

class TestPDFLoaderEdgeCases:
    def test_extract_text_from_missing_file(self):
        from app.services.pdf_loader import PDFLoader, PDFLoaderError

        loader = PDFLoader(documents_path="data/documents")
        with pytest.raises(PDFLoaderError, match="PDF file not found"):
            loader.extract_text("non_existent_file.pdf")

    def test_extract_text_empty_file(self, tmp_path):
        from app.services.pdf_loader import PDFLoader, PDFLoaderError

        loader = PDFLoader(documents_path=str(tmp_path))
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")

        with pytest.raises(PDFLoaderError, match="Failed to extract text from PDF"):
            loader.extract_text(str(empty_pdf))

    def test_extract_text_malformed_file(self, tmp_path):
        from app.services.pdf_loader import PDFLoader, PDFLoaderError

        loader = PDFLoader(documents_path=str(tmp_path))
        malformed_pdf = tmp_path / "malformed.pdf"
        malformed_pdf.write_text("This is not a PDF file")

        with pytest.raises(PDFLoaderError, match="Failed to extract text from PDF"):
            loader.extract_text(str(malformed_pdf))

    def test_extract_text_no_langchain(self, monkeypatch, tmp_path):
        from app.services.pdf_loader import PDFLoader, PDFLoaderError
        import app.services.pdf_loader as pdf_loader_mod

        monkeypatch.setattr(pdf_loader_mod, 'PyPDFLoader', None)
        loader = PDFLoader(documents_path=str(tmp_path))
        dummy_pdf = tmp_path / "dummy.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4\n")

        with pytest.raises(PDFLoaderError, match="LangChain PDF loader is not installed"):
            loader.extract_text(str(dummy_pdf))

    def test_extract_text_from_bytes_empty(self, tmp_path):
        from app.services.pdf_loader import PDFLoader, PDFLoaderError

        loader = PDFLoader(documents_path=str(tmp_path))
        with pytest.raises(PDFLoaderError, match="Failed to extract text from PDF"):
            loader.extract_text_from_bytes(b"", "empty.pdf")
