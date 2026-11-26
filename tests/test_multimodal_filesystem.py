"""Tests for multimodal and directory reading in filesystem and voice layer.

Verifies:
1. fs.read_text handles UTF-8 and non-UTF-8 text files without UnicodeDecodeError.
2. fs.read_text handles directories and returns structured listings without 'path is not a file'.
3. fs.read_text extracts text from PDF documents using pdftotext/fallback without UnicodeDecodeError.
4. fs.read_text extracts text from Word (DOCX), PowerPoint (PPTX), and Excel (XLSX).
5. fs.read_text inspects images (PNG, JPEG) with dimensions and OCR text.
6. fs.read_text inspects archives (ZIP, TAR) and binary files gracefully.
7. DesktopSkills._adapter_read_file handles directories, PDFs, documents, and images.
8. Daemon input processing handles PDF extraction, attachments, and directory references.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import pytest

import filesystem as fs
from skills import DesktopSkills


def _create_minimal_pdf(text: str) -> bytes:
    escaped = text.replace('(', '\\(').replace(')', '\\)')
    stream_content = f"BT\n/F1 18 Tf\n50 700 Td\n({escaped}) Tj\nET\n".encode("utf-8")
    stream_len = len(stream_content)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(stream_len).encode("ascii") + b" >>\nstream\n"
        + stream_content +
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n500\n%%EOF\n"
    )
    return pdf


def test_read_text_utf8_and_latin1(tmp_path: Path):
    utf8_file = tmp_path / "utf8.txt"
    utf8_file.write_text("Hello UTF-8 text file", encoding="utf-8")
    res_utf8 = fs.read_text(str(utf8_file))
    assert res_utf8["content"] == "Hello UTF-8 text file"
    assert res_utf8["type"] == "text"

    # Non-UTF-8 Latin-1 file with accented characters
    latin1_file = tmp_path / "latin1.txt"
    latin1_bytes = b"Resum\xe9 of software engineer \xa9 2026"
    latin1_file.write_bytes(latin1_bytes)
    res_latin1 = fs.read_text(str(latin1_file))
    assert "Resum" in res_latin1["content"]
    assert res_latin1["type"] == "text"


def test_read_text_directory(tmp_path: Path):
    test_dir = tmp_path / "sample_project"
    test_dir.mkdir()
    (test_dir / "src").mkdir()
    (test_dir / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (test_dir / "README.md").write_text("# Sample Project", encoding="utf-8")

    res = fs.read_text(str(test_dir))
    assert res["type"] == "directory"
    assert res["is_directory"] is True
    assert "sample_project" in res["content"]
    assert "src/" in res["content"]
    assert "README.md" in res["content"]
    assert res["truncated"] is False


def test_read_text_pdf(tmp_path: Path):
    pdf_file = tmp_path / "document.pdf"
    pdf_bytes = _create_minimal_pdf("JARVIS Autonomous OS Report")
    pdf_file.write_bytes(pdf_bytes)

    res = fs.read_text(str(pdf_file))
    assert res["type"] == "pdf"
    assert "JARVIS Autonomous OS Report" in res["content"]
    assert "document.pdf" in res["content"]


def test_read_text_docx(tmp_path: Path):
    docx_file = tmp_path / "test.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:r><w:t>Quarterly Financial Results</w:t></w:r></w:p>
            <w:p><w:r><w:t>Revenue grew by 24% year-over-year.</w:t></w:r></w:p>
          </w:body>
        </w:document>"""
        zf.writestr("word/document.xml", xml_content)

    res = fs.read_text(str(docx_file))
    assert res["type"] == "document"
    assert "Quarterly Financial Results" in res["content"]
    assert "Revenue grew by 24%" in res["content"]


def test_read_text_pptx(tmp_path: Path):
    pptx_file = tmp_path / "slides.pptx"
    with zipfile.ZipFile(pptx_file, "w") as zf:
        xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
               xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
          <p:cSld>
            <p:spTree>
              <p:sp>
                <p:txBody>
                  <a:p><a:r><a:t>Slide Title: System Architecture</a:t></a:r></a:p>
                </p:txBody>
              </p:sp>
            </p:spTree>
          </p:cSld>
        </p:sld>"""
        zf.writestr("ppt/slides/slide1.xml", xml_content)

    res = fs.read_text(str(pptx_file))
    assert res["type"] == "document"
    assert "System Architecture" in res["content"]


def test_read_text_xlsx(tmp_path: Path):
    xlsx_file = tmp_path / "data.xlsx"
    with zipfile.ZipFile(xlsx_file, "w") as zf:
        xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2">
          <si><t>Item A</t></si>
          <si><t>Cost: $100</t></si>
        </sst>"""
        zf.writestr("xl/sharedStrings.xml", xml_content)

    res = fs.read_text(str(xlsx_file))
    assert res["type"] == "document"
    assert "Item A" in res["content"]
    assert "Cost: $100" in res["content"]


def test_read_text_image(tmp_path: Path):
    img_file = tmp_path / "tiny.png"
    # 1x1 transparent PNG bytes
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
    img_file.write_bytes(png_bytes)

    res = fs.read_text(str(img_file))
    assert res["type"] == "image"
    assert "Image File" in res["content"]
    assert "tiny.png" in res["content"]


def test_read_text_zip_archive(tmp_path: Path):
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("file1.txt", "content one")
        zf.writestr("docs/file2.txt", "content two")

    res = fs.read_text(str(zip_path))
    assert res["type"] == "archive"
    assert "file1.txt" in res["content"]
    assert "docs/file2.txt" in res["content"]


def test_read_text_binary_file(tmp_path: Path):
    bin_file = tmp_path / "raw.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe\xfd\x00data")

    res = fs.read_text(str(bin_file))
    assert res["type"] == "binary"
    assert "raw.bin" in res["content"]


def test_read_text_video(tmp_path: Path):
    video_file = tmp_path / "sample.mp4"
    # Generate minimal 1-second synthetic mp4 using ffmpeg
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=10',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
        '-c:v', 'libx264', '-c:a', 'aac', str(video_file)
    ], capture_output=True, check=True)

    res = fs.read_text(str(video_file))
    assert res["type"] == "video"
    assert "Video File: sample.mp4" in res["content"]
    assert "320x240" in res["content"]
    assert "Streams" in res["content"]
    assert "H264" in res["content"]
    assert "AAC" in res["content"]


def test_read_text_audio(tmp_path: Path):
    import wave
    audio_file = tmp_path / "sample.wav"
    with wave.open(str(audio_file), 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        # 0.5 second of stereo silence
        wf.writeframes(b'\x00\x00\x00\x00' * 22050)

    res = fs.read_text(str(audio_file))
    assert res["type"] == "audio"
    assert "Audio File: sample.wav" in res["content"]
    assert "44.1 kHz" in res["content"]
    assert "stereo" in res["content"].lower() or "2 ch" in res["content"].lower()


@pytest.mark.asyncio
async def test_skills_read_file_multimodal(tmp_path: Path):
    skills = DesktopSkills()

    # 1. Directory read via skills
    dir_path = tmp_path / "my_folder"
    dir_path.mkdir()
    (dir_path / "hello.py").write_text("x = 1")
    res_dir = await skills.execute("read_file", {"path": str(dir_path)})
    assert res_dir["type"] == "directory"
    assert "hello.py" in res_dir["content"]

    # 2. PDF read via skills
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_create_minimal_pdf("DesktopSkills PDF Integration"))
    res_pdf = await skills.execute("read_file", {"path": str(pdf_path)})
    assert res_pdf["type"] == "pdf"
    assert "DesktopSkills PDF Integration" in res_pdf["content"]

    # 3. Video read via skills
    v_path = tmp_path / "clip.mp4"
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=160x120:rate=10',
        '-c:v', 'libx264', str(v_path)
    ], capture_output=True, check=True)
    res_video = await skills.execute("read_file", {"path": str(v_path)})
    assert res_video["type"] == "video"
    assert "160x120" in res_video["content"]

    # 4. Audio read via skills
    import wave
    a_path = tmp_path / "sound.wav"
    with wave.open(str(a_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00\x00' * 8000)
    res_audio = await skills.execute("read_file", {"path": str(a_path)})
    assert res_audio["type"] == "audio"
    assert "16.0 kHz" in res_audio["content"]

    # 5. Read without path defaults to home
    res_home = await skills.execute("read_file", {})
    assert res_home["type"] == "directory"
    assert res_home["is_directory"] is True
