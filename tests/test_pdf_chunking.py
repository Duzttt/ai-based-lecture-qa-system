"""
Tests for course metadata extraction and metadata-aware chunking.

The cover page of a course outline PDF typically contains fields that never
appear again in the lecture slides (course code, lecturer, department).
Prepending these fields to every chunk dramatically improves retrieval recall
for metadata-style questions like "Who is the author?".
"""

from typing import Any, Dict, List


def _make_page(page_num: int, text: str) -> Dict[str, Any]:
    return {"page": page_num, "text": text}


def _make_uitm_cover() -> List[Dict[str, Any]]:
    return [
        _make_page(
            1,
            (
                "INTRODUCTION\n"
                "TO AGENTS\n"
                "BAXI 3113 \u2013 INTELLIGENT AGENT\n"
                "Dr. Nur Zareen Zulkarnain\n"
                "Department of Intelligent Computing  and Analytics (ICA)\n"
                "     DG/1 -18\n"
                "     zareen@utem.edu.my\n"
            ),
        ),
        _make_page(
            2,
            (
                "Students will be exposed to the concept of intelligent agent "
                "and multiagent systems including:\n"
                " theory of agents\n"
                " common agent architectures\n"
                " methods of cooperationmethods of communication\n"
                "potential applications for agentsCOURSE OVERVIEW\n"
            ),
        ),
        _make_page(
            3,
            (
                "COURSE LEARNING OUTCOMES\n"
                "Upon completing this subject, you should be able to:\n"
                "CLO1:    Evaluate various concepts of intelligent agent.\n"
                "CLO2:    Organise effective solution steps in solving intelligent agent problems.\n"
                "CLO3:    Manipulate techniques of intelligent agents for problem solving.\n"
            ),
        ),
    ]


def _make_lecture_only_pages() -> List[Dict[str, Any]]:
    return [
        _make_page(
            1, "GAME OF CHICKEN to drop out of the game by jumping out of the car."
        ),
        _make_page(2, "MULTIAGENT SYSTEM is one that consists of a number of agents."),
    ]


class TestExtractCourseMetadata:
    def test_extracts_course_code_from_cover(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata(_make_uitm_cover())
        assert "BAXI 3113" in meta["course_code"]

    def test_extracts_lecturer_name_from_cover(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata(_make_uitm_cover())
        assert "Nur Zareen" in meta["lecturer"]
        assert "Zulkarnain" in meta["lecturer"]

    def test_extracts_department_from_cover(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata(_make_uitm_cover())
        assert "Intelligent Computing" in meta["department"]
        assert "Analytics" in meta["department"]

    def test_extracts_course_title_from_cover(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata(_make_uitm_cover())
        assert "INTELLIGENT AGENT" in meta["course_title"].upper()

    def test_returns_empty_fields_when_no_metadata(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata(_make_lecture_only_pages())
        assert meta["course_code"] == ""
        assert meta["lecturer"] == ""
        assert meta["department"] == ""

    def test_handles_empty_pages_list(self):
        from app.services.pdf_chunking import extract_course_metadata

        meta = extract_course_metadata([])
        assert meta == {
            "course_code": "",
            "course_title": "",
            "lecturer": "",
            "department": "",
            "faculty": "",
        }

    def test_extracts_with_explicit_course_code_label(self):
        from app.services.pdf_chunking import extract_course_metadata

        pages = [
            _make_page(
                1,
                "Course Code: CSC510\nCourse Title: Machine Learning\nLecturer: Dr. Alice Wong\n"
                "Department of Computer Science",
            )
        ]
        meta = extract_course_metadata(pages)
        assert meta["course_code"] == "CSC510"
        assert "Alice Wong" in meta["lecturer"]
        assert "Computer Science" in meta["department"]

    def test_extracts_malay_lecturer_keyword(self):
        from app.services.pdf_chunking import extract_course_metadata

        pages = [
            _make_page(
                1,
                "Kod Kursus: CSC510\nPensyarah: Prof. Madya Dr. Lim Wei Sheng\nJabatan Sains Komputer",
            )
        ]
        meta = extract_course_metadata(pages)
        assert "Lim Wei Sheng" in meta["lecturer"]


class TestChunkPdfWithMetadataPrepend:
    def test_metadata_prepended_to_every_chunk(self, monkeypatch, tmp_path):
        from app.services import pdf_chunking

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            pdf_chunking, "read_pdf_pages", lambda _path: _make_uitm_cover()
        )

        chunks = pdf_chunking.chunk_pdf_with_metadata(
            pdf_path=str(fake_pdf),
            chunk_size=200,
            overlap=20,
        )

        assert len(chunks) > 0
        for chunk in chunks:
            assert "BAXI 3113" in chunk["text"]
            assert "Zulkarnain" in chunk["text"]

    def test_first_chunk_contains_lecturer_and_department(self, monkeypatch, tmp_path):
        from app.services import pdf_chunking

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            pdf_chunking, "read_pdf_pages", lambda _path: _make_uitm_cover()
        )

        chunks = pdf_chunking.chunk_pdf_with_metadata(
            pdf_path=str(fake_pdf),
            chunk_size=200,
            overlap=20,
        )

        assert len(chunks) > 0
        first = chunks[0]["text"]
        assert "Nur Zareen" in first
        assert "Intelligent Computing" in first or "ICA" in first

    def test_metadata_header_absent_when_no_metadata_found(self, monkeypatch, tmp_path):
        from app.services import pdf_chunking

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            pdf_chunking, "read_pdf_pages", lambda _path: _make_lecture_only_pages()
        )

        chunks = pdf_chunking.chunk_pdf_with_metadata(
            pdf_path=str(fake_pdf),
            chunk_size=500,
            overlap=50,
        )

        for chunk in chunks:
            assert "[Course Metadata]" not in chunk["text"]

    def test_opt_out_disables_prepending(self, monkeypatch, tmp_path):
        from app.services import pdf_chunking

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            pdf_chunking, "read_pdf_pages", lambda _path: _make_uitm_cover()
        )

        chunks = pdf_chunking.chunk_pdf_with_metadata(
            pdf_path=str(fake_pdf),
            chunk_size=200,
            overlap=20,
            prepend_course_metadata=False,
        )

        for chunk in chunks:
            assert "[Course Metadata]" not in chunk["text"]

    def test_chunks_preserve_source_and_page_metadata(self, monkeypatch, tmp_path):
        from app.services import pdf_chunking

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            pdf_chunking, "read_pdf_pages", lambda _path: _make_uitm_cover()
        )

        chunks = pdf_chunking.chunk_pdf_with_metadata(
            pdf_path=str(fake_pdf),
            chunk_size=200,
            overlap=20,
        )

        for chunk in chunks:
            assert chunk["source"] == "fake.pdf"
            assert isinstance(chunk["page"], int)
            assert chunk["page"] >= 1
