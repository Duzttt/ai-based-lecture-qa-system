from app.config import Settings


def test_pdf_parser_defaults_to_pypdf():
    s = Settings()
    assert s.PDF_PARSER == "pypdf"


def test_pdf_parser_accepts_opendataloader():
    s = Settings(PDF_PARSER="opendataloader")
    assert s.PDF_PARSER == "opendataloader"


def test_pdf_parser_invalid_falls_back_to_pypdf():
    s = Settings(PDF_PARSER="invalid")
    assert s.PDF_PARSER == "pypdf"
