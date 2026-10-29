"""Pruebas unitarias de lógica de negocio y seguridad (sin dependencias de servidor HTTP).

Diseñado para ejecutarse con pytest tanto localmente como en GitHub Actions (Rúbrica: 15%).
"""
import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import catalog  # noqa: E402
from backups import get_backup_path, human_size  # noqa: E402
from posts import parse_price, sniff_image  # noqa: E402
from security import (  # noqa: E402
    check_password,
    clean_text,
    hash_code,
    hash_password,
    hash_token,
    is_institutional,
    new_code,
    normalize_email,
    password_problem,
    sniff_document,
)


class TestEmailAndSecurity:
    def test_normalize_email_valid(self):
        assert normalize_email("AL123456@edu.uaa.mx ") == "al123456@edu.uaa.mx"
        assert normalize_email("usuario.test@gmail.com") == "usuario.test@gmail.com"

    def test_normalize_email_invalid(self):
        assert normalize_email("no-es-correo") is None
        assert normalize_email("@sin-usuario.com") is None
        assert normalize_email(None) is None
        assert normalize_email(12345) is None

    def test_is_institutional(self):
        assert is_institutional("al350114@edu.uaa.mx") is True
        assert is_institutional("profesor@edu.uaa.mx") is True
        # Rechazar dominios falsos o suplantaciones
        assert is_institutional("alguien@gmail.com") is False
        assert is_institutional("hacker@edu.uaa.mx.evil.com") is False
        assert is_institutional("al@uaa.mx") is False

    def test_password_problem_criteria(self):
        # Mínimo de caracteres (config.PASSWORD_MIN = 8)
        assert password_problem("corta1") is not None
        # Letras y al menos un número
        assert password_problem("sololetraslargas") is not None
        assert password_problem("1234567890") is not None
        # Contraseña válida
        assert password_problem("claveSegura123") is None

    def test_password_hashing_and_verification(self):
        pw = "MiClaveSecreta99"
        pw_hash = hash_password(pw)
        assert pw_hash != pw
        user_mock = {"password_hash": pw_hash}
        assert check_password(user_mock, pw) is True
        assert check_password(user_mock, "claveIncorrecta") is False
        assert check_password(None, pw) is False

    def test_otp_code_generation(self):
        for _ in range(20):
            code = new_code()
            assert len(code) == 6
            assert code.isdigit()

    def test_hashing_tokens_deterministic(self):
        h1 = hash_code("test@edu.uaa.mx", "123456")
        h2 = hash_code("test@edu.uaa.mx", "123456")
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex
        assert hash_token("token_abc") == hash_token("token_abc")

    def test_clean_text_sanitization(self):
        assert clean_text("   Hola mundo   ", 100) == "Hola mundo"
        assert clean_text("Texto con \x00 caracteres \x1f de control", 100) == "Texto con  caracteres  de control"
        assert clean_text("Texto largo que excede límite", 5) == "Texto"
        assert clean_text("", 100, required=True) is None
        assert clean_text("", 100, required=False) == ""
        assert clean_text(1234, 100, required=True) is None


class TestDocumentAndImageSniffing:
    def test_sniff_image_valid_formats(self):
        jpg_header = b"\xff\xd8\xff" + b"\x00" * 20
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        webp_header = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 10
        assert sniff_image(jpg_header) == "jpg"
        assert sniff_image(png_header) == "png"
        assert sniff_image(webp_header) == "webp"

    def test_sniff_image_invalid_format(self):
        exe_file = b"MZ\x90\x00\x03\x00\x00\x00"
        txt_file = b"Este es un archivo de texto plano."
        assert sniff_image(exe_file) is None
        assert sniff_image(txt_file) is None

    def test_sniff_document_pdf_and_images(self):
        pdf_header = b"%PDF-1.7\n" + b"\x00" * 20
        jpg_header = b"\xff\xd8\xff" + b"\x00" * 20
        assert sniff_document(pdf_header) == "pdf"
        assert sniff_document(jpg_header) == "jpg"
        assert sniff_document(b"binario random") is None


class TestCatalogAndCarreras:
    def test_catalog_structure(self):
        assert len(catalog.CENTROS) >= 7
        assert "Centro de Ciencias Básicas" in catalog.CENTROS
        assert "Centro de Ciencias de la Salud" in catalog.CENTROS

    def test_carrera_to_centro_mapping(self):
        centro_sistemas = catalog.centro_de("Ingeniería en Sistemas Computacionales")
        assert centro_sistemas == "Centro de Ciencias Básicas"

        centro_medicina = catalog.centro_de("Médico Cirujano")
        assert centro_medicina == "Centro de Ciencias de la Salud"

        centro_desconocido = catalog.centro_de("Carrera Inexistente Falsa")
        assert centro_desconocido is None


class TestPriceAndBackups:
    def test_parse_price(self):
        assert parse_price("100") == 10000  # $100.00 MXN en centavos
        assert parse_price("50.50") == 5050
        assert parse_price("0") == 0
        assert parse_price("-20") is None
        assert parse_price("invalido") is None
        assert parse_price("1,000.50") is None  # o coma decimal según formato

    def test_human_size(self):
        assert human_size(500) == "500 B"
        assert human_size(1024) == "1.0 KB"
        assert human_size(1024 * 1024 * 2) == "2.0 MB"

    def test_get_backup_path_security(self):
        # Nombres que intenten Directory Traversal deben ser rechazados
        assert get_backup_path("../../etc/passwd") is None
        assert get_backup_path("archivo_cualquiera.txt") is None
        assert get_backup_path("ecogallo_backup_invalido.tar.gz") is None
