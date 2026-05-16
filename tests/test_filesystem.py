"""Tests for filesystem tools (list and read bank statements)."""

import json
from unittest.mock import patch

from src.tools.filesystem import list_bank_statements, read_bank_statement


class TestListBankStatements:
    """Tests for listing bank statement files."""

    def test_lists_csv_files(self, sample_csv, tmp_statements_dir):
        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements(""))
            assert result["total_files"] == 1
            assert result["files"][0]["name"] == "bancolombia_mayo.csv"
            assert result["files"][0]["extension"] == ".csv"

    def test_lists_multiple_formats(
        self, sample_csv, sample_excel, sample_image, tmp_statements_dir
    ):
        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements(""))
            assert result["total_files"] == 3
            extensions = {f["extension"] for f in result["files"]}
            assert extensions == {".csv", ".xlsx", ".png"}

    def test_subdirectory_filter(self, tmp_statements_dir):
        # Create a subdirectory with a file
        sub = tmp_statements_dir / "mayo_2026"
        sub.mkdir()
        (sub / "test.csv").write_text("a,b,c\n1,2,3")

        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements("mayo_2026"))
            assert result["total_files"] == 1

    def test_nonexistent_directory(self, tmp_statements_dir):
        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements("does_not_exist"))
            assert "error" in result

    def test_empty_directory(self, tmp_statements_dir):
        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements(""))
            assert result["total_files"] == 0

    def test_ignores_unsupported_files(self, tmp_statements_dir):
        (tmp_statements_dir / "readme.txt").write_text("ignore me")
        (tmp_statements_dir / "data.json").write_text("{}")
        (tmp_statements_dir / "real.csv").write_text("a,b\n1,2")

        with patch("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir):
            result = json.loads(list_bank_statements(""))
            assert result["total_files"] == 1  # only .csv


class TestReadBankStatement:
    """Tests for reading bank statement content."""

    def test_reads_csv(self, sample_csv):
        result = json.loads(read_bank_statement(str(sample_csv)))
        assert result["type"] == "text"
        assert "EXITO" in result["content"]

    def test_reads_excel(self, sample_excel):
        result = json.loads(read_bank_statement(str(sample_excel)))
        assert result["type"] == "text"
        assert "Movimientos" in result["content"]

    def test_reads_image(self, sample_image):
        result = json.loads(read_bank_statement(str(sample_image)))
        assert result["type"] == "image"
        assert "data" in result

    def test_file_not_found_returns_error(self):
        result = json.loads(read_bank_statement("/nonexistent/file.pdf"))
        assert "error" in result

    def test_unsupported_format_returns_error(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")
        result = json.loads(read_bank_statement(str(txt)))
        assert "error" in result
        assert "Unsupported" in result["error"]
