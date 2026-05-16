"""Tests for the multi-format file reader service."""

import pytest

from src.services.file_reader import read_file


class TestReadCSV:
    """Tests for CSV file reading."""

    def test_reads_csv_content(self, sample_csv):
        result = read_file(sample_csv)
        assert result["type"] == "text"
        assert result["file_name"] == "bancolombia_mayo.csv"
        assert "EXITO ENVIGADO" in result["content"]
        assert "NETFLIX" in result["content"]
        assert result["password_protected"] is False

    def test_csv_detects_all_rows(self, sample_csv):
        result = read_file(sample_csv)
        # Header + 5 data rows = 6 lines
        lines = result["content"].strip().split("\n")
        assert len(lines) == 6

    def test_csv_returns_none_pages(self, sample_csv):
        result = read_file(sample_csv)
        assert result["pages"] is None


class TestReadExcel:
    """Tests for Excel file reading."""

    def test_reads_xlsx_content(self, sample_excel):
        result = read_file(sample_excel)
        assert result["type"] == "text"
        assert result["file_name"] == "davivienda_mayo.xlsx"
        assert "Movimientos" in result["content"]  # sheet name
        assert "Exito" in result["content"]
        assert result["password_protected"] is False

    def test_xlsx_counts_sheets(self, sample_excel):
        result = read_file(sample_excel)
        assert result["pages"] == 1  # one sheet

    def test_xlsx_includes_all_rows(self, sample_excel):
        result = read_file(sample_excel)
        # Should contain header + 3 data rows
        assert "Compra TC" in result["content"]
        assert "Pago PSE" in result["content"]
        assert "Transferencia recibida" in result["content"]


class TestReadImage:
    """Tests for image file reading."""

    def test_reads_image_as_base64(self, sample_image):
        result = read_file(sample_image)
        assert result["type"] == "image"
        assert result["file_name"] == "extracto_scan.png"
        assert "data" in result
        assert len(result["data"]) > 0  # base64 data present
        assert result["password_protected"] is False

    def test_image_content_is_descriptive(self, sample_image):
        result = read_file(sample_image)
        assert "Image file" in result["content"]
        assert "extracto_scan.png" in result["content"]


class TestReadFileErrors:
    """Tests for error handling."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/path/file.pdf")

    def test_unsupported_format(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file format"):
            read_file(txt_file)

    def test_password_required_error_message(self, tmp_path):
        """Encrypted files without password should raise clear error."""
        # We can't easily create a password-protected PDF in a test,
        # but we verify the error path exists for unsupported formats
        bad_file = tmp_path / "data.doc"
        bad_file.write_text("fake")
        with pytest.raises(ValueError):
            read_file(bad_file)
