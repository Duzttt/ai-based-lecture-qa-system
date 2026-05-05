def test_get_pdf_parser_returns_pypdf_by_default(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "pypdf")
    from app.services.pdf_indexing import get_pdf_parser

    parser = get_pdf_parser()
    assert parser["name"] == "pypdf"
    assert callable(parser["read_text"])
    assert callable(parser["read_pages"])
    assert callable(parser["chunk_with_metadata"])


def test_get_pdf_parser_returns_opendataloader(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "opendataloader")
    from app.services.pdf_indexing import get_pdf_parser

    parser = get_pdf_parser()
    assert parser["name"] == "opendataloader"


def test_get_pdf_parser_unknown_falls_back_to_pypdf(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "unknown")
    from app.services.pdf_indexing import get_pdf_parser

    parser = get_pdf_parser()
    assert parser["name"] == "pypdf"
