"""Shared test fixtures for YNAB MCP Orchestrator tests."""

import csv
import json
from typing import Any

import openpyxl
import pytest


@pytest.fixture
def tmp_statements_dir(tmp_path):
    """Create a temporary statements directory with sample files."""
    statements = tmp_path / "extractos"
    statements.mkdir()
    return statements


@pytest.fixture(autouse=True)
def mock_statements_dir(monkeypatch, tmp_statements_dir):
    """Patch STATEMENTS_DIR in modules to point to the temporary test directory."""
    monkeypatch.setattr("src.services.file_reader.STATEMENTS_DIR", tmp_statements_dir)
    monkeypatch.setattr("src.tools.filesystem.STATEMENTS_DIR", tmp_statements_dir)


@pytest.fixture
def sample_csv(tmp_statements_dir):
    """Create a sample CSV bank statement."""
    csv_path = tmp_statements_dir / "bancolombia_mayo.csv"
    rows = [
        ["Fecha", "Descripción", "Valor", "Tipo"],
        ["15/05/2026", "COMPRA EN EXITO ENVIGADO", "-150500", "Débito"],
        ["14/05/2026", "TRANSFERENCIA NÓMINA", "3500000", "Crédito"],
        ["13/05/2026", "NETFLIX.COM", "-45900", "Débito"],
        ["12/05/2026", "RETIRO ATM CENTRO", "-200000", "Débito"],
        ["11/05/2026", "UBER *TRIP", "-12300", "Débito"],
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def sample_excel(tmp_statements_dir):
    """Create a sample Excel bank statement."""
    xlsx_path = tmp_statements_dir / "davivienda_mayo.xlsx"
    wb = openpyxl.Workbook()
    ws: Any = wb.active
    ws.title = "Movimientos"
    ws.append(["Fecha", "Descripción", "Monto", "Saldo"])
    ws.append(["15/05/2026", "Compra TC *1234 Exito", -85000, 1200000])
    ws.append(["14/05/2026", "Pago PSE Servicios", -230000, 1285000])
    ws.append(["13/05/2026", "Transferencia recibida", 500000, 1515000])
    wb.save(str(xlsx_path))
    return xlsx_path


@pytest.fixture
def sample_image(tmp_statements_dir):
    """Create a minimal PNG image (1x1 white pixel)."""
    # Minimal valid PNG file
    import struct
    import zlib

    img_path = tmp_statements_dir / "extracto_scan.png"

    def create_minimal_png():
        signature = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT chunk
        raw_data = b"\x00\xff\xff\xff"  # filter byte + RGB white pixel
        compressed = zlib.compress(raw_data)
        idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
        idat = (
            struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)
        )

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return signature + ihdr + idat + iend

    img_path.write_bytes(create_minimal_png())
    return img_path


@pytest.fixture
def valid_transactions_json():
    """A valid JSON string of transactions."""
    transactions = [
        {
            "date": "2026-05-15",
            "amount": -150500,
            "payee_name": "Exito Envigado",
            "memo": "Compra TC *1234",
            "cleared": "uncleared",
            "approved": False,
            "account_id": "test-account-uuid",
        },
        {
            "date": "2026-05-14",
            "amount": 3500000,
            "payee_name": "Nómina Empresa",
            "memo": "Transferencia nómina mayo",
            "cleared": "uncleared",
            "approved": False,
            "account_id": "test-account-uuid",
        },
    ]
    return json.dumps(transactions)


@pytest.fixture
def invalid_transactions_json():
    """A JSON string with invalid transactions."""
    transactions = [
        {
            "date": "2026-05-15",
            # missing 'amount' — required field
            "payee_name": "Test Payee",
        },
        {
            "date": "2026-05-14",
            "amount": "not-a-number",  # wrong type
        },
    ]
    return json.dumps(transactions)
