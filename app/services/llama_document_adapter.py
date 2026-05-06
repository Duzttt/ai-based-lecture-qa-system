from typing import Any, Dict, List

from llama_index.core import Document


class LlamaDocumentAdapter:
    """将现有PDF加载器输出转换为LlamaIndex Document格式"""

    @staticmethod
    def from_pdf_loader(pdf_output: List[Dict[str, Any]]) -> List[Document]:
        """
        将PDF加载器输出转换为LlamaIndex Document列表

        Args:
            pdf_output: PDF加载器输出的字典列表，每个字典包含text, source, page等字段

        Returns:
            LlamaIndex Document列表
        """
        documents = []

        for item in pdf_output:
            text = item.get("text", "")
            source = item.get("source", "unknown")
            page = item.get("page")

            # 创建元数据
            metadata = {"source": source, "page": page}

            # 创建LlamaIndex Document
            doc_id = f"{source}_page_{page}" if page is not None else source
            doc = Document(text=text, metadata=metadata, doc_id=doc_id)
            documents.append(doc)

        return documents
