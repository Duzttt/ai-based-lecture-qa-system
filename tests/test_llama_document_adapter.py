from app.services.llama_document_adapter import LlamaDocumentAdapter


def test_from_pdf_loader_with_valid_output():
    """测试PDF加载器输出转换"""
    # 模拟PDF加载器输出
    pdf_output = [
        {"text": "这是第一页内容", "source": "test.pdf", "page": 1},
        {"text": "这是第二页内容", "source": "test.pdf", "page": 2},
    ]

    documents = LlamaDocumentAdapter.from_pdf_loader(pdf_output)

    assert len(documents) == 2
    assert documents[0].text == "这是第一页内容"
    assert documents[0].metadata["source"] == "test.pdf"
    assert documents[0].metadata["page"] == 1


def test_from_pdf_loader_with_empty_output():
    """测试空PDF加载器输出"""
    pdf_output = []

    documents = LlamaDocumentAdapter.from_pdf_loader(pdf_output)

    assert len(documents) == 0
