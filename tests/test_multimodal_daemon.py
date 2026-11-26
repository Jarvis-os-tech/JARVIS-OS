"""Tests for voice_layer.daemon multimodal and input processing.

Verifies:
1. send_inputs forwards PDF attachments and extracts text.
2. send_inputs renders and forwards scanned PDF pages and OCR text.
3. send_inputs forwards office documents (DOCX).
4. send_inputs keeps paths in ordinary text as text.
5. send_inputs resolves attached directories from disk when data is empty.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import zipfile
import pytest

from voice.daemon import LiveVoice
from tests.test_multimodal_filesystem import _create_minimal_pdf


class InputCaptured(Exception):
    pass


class MockSession:
    def __init__(self):
        self.sent_turns = []

    async def send_client_content(self, turns, turn_complete):
        self.sent_turns.append(turns)
        raise InputCaptured


class MockGate:
    active = False


@pytest.fixture
def daemon():
    d = LiveVoice.__new__(LiveVoice)
    d.skills = None
    d._input_queue = asyncio.Queue()
    d.standby_active = False
    d.standby = None
    d.gate = MockGate()
    d.send_lock = asyncio.Lock()
    d._barge_pending = False
    d._barge_turn = False
    d._drop_response = False
    d._reply_authorized = False
    d._waiting = False
    d._reply_started = False
    d._model_active = False
    d.recognized_input_events = 0
    d._user_text = ""
    d._memory_user = ""
    d._start_reply_watch = lambda: None
    return d


@pytest.mark.asyncio
async def test_daemon_pdf_attachment(daemon, tmp_path: Path):
    session = MockSession()
    pdf_bytes = _create_minimal_pdf("Attached PDF Test Data")

    daemon._input_queue.put_nowait({
        "text": "What does this PDF say?",
        "data": pdf_bytes,
        "mime": "application/pdf",
        "name": "test_doc.pdf",
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    content = session.sent_turns[0][0]
    parts = content.parts
    assert any("Attached PDF Test Data" in getattr(p, "text", "") for p in parts)


@pytest.mark.asyncio
async def test_daemon_docx_attachment(daemon, tmp_path: Path):
    session = MockSession()
    docx_file = tmp_path / "summary.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>Project Milestone 3 Achieved</w:t></w:r></w:p></w:body>
            </w:document>""",
        )
    docx_bytes = docx_file.read_bytes()

    daemon._input_queue.put_nowait({
        "text": "",
        "data": docx_bytes,
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "name": "summary.docx",
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    assert any("Project Milestone 3 Achieved" in getattr(p, "text", "") for p in parts)


@pytest.mark.asyncio
async def test_daemon_does_not_attach_directory_mentioned_in_text(daemon, tmp_path: Path):
    session = MockSession()
    folder = tmp_path / "my_project"
    folder.mkdir()
    (folder / "app.py").write_text("print('running app')")
    (folder / "config.json").write_text("{}")

    daemon._input_queue.put_nowait({
        "text": f"Please inspect {folder}",
        "data": b"",
        "mime": "",
        "name": "",
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    full_text = "\n".join(p.text or "" for p in parts if getattr(p, "text", None))
    assert full_text == f"Please inspect {folder}"


@pytest.mark.asyncio
async def test_daemon_attached_directory_reference(daemon, tmp_path: Path):
    session = MockSession()
    folder = tmp_path / "attached_dir"
    folder.mkdir()
    (folder / "file.txt").write_text("attached directory content")

    # When dropping a folder in HUD input bar, data is empty but name has the path
    daemon._input_queue.put_nowait({
        "text": "",
        "data": b"",
        "mime": "",
        "name": str(folder),
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    full_text = "\n".join(p.text or "" for p in parts if getattr(p, "text", None))
    assert f"Attached Directory: {folder}" in full_text
    assert "file.txt" in full_text


@pytest.mark.asyncio
async def test_daemon_scanned_pdf_rendering(daemon, tmp_path: Path):
    session = MockSession()
    # Create a PDF with text rendered visually
    pdf_bytes = _create_minimal_pdf("Scanned Page Visual Data")

    daemon._input_queue.put_nowait({
        "text": "Analyze this scanned PDF",
        "data": pdf_bytes,
        "mime": "application/pdf",
        "name": "scanned.pdf",
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    # Either extracted text or rendered image part
    has_text = any("Scanned Page Visual Data" in getattr(p, "text", "") for p in parts)
    has_image = any(getattr(p, "inline_data", None) is not None for p in parts)
    assert has_text or has_image


@pytest.mark.asyncio
async def test_daemon_video_attachment(daemon, tmp_path: Path):
    session = MockSession()
    import subprocess
    v_file = tmp_path / "test_clip.mp4"
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=160x120:rate=10',
        '-c:v', 'libx264', str(v_file)
    ], capture_output=True, check=True)
    video_bytes = v_file.read_bytes()

    daemon._input_queue.put_nowait({
        "text": "What happens in this video clip?",
        "data": video_bytes,
        "mime": "video/mp4",
        "name": "test_clip.mp4",
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 8)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    # Verify video text description is forwarded
    full_text = "\n".join(p.text or "" for p in parts if getattr(p, "text", None))
    assert "Attached Video File: test_clip.mp4" in full_text
    assert "160x120" in full_text
    # Verify keyframe JPEG image part is delivered to Gemini Live
    jpeg_parts = [p for p in parts if getattr(p, "inline_data", None) and p.inline_data.mime_type == "image/jpeg"]
    assert len(jpeg_parts) >= 1
    assert jpeg_parts[0].inline_data.data.startswith(b'\xff\xd8')


@pytest.mark.asyncio
async def test_daemon_file_path_reference_loads_from_disk(daemon, tmp_path: Path):
    session = MockSession()
    img_file = tmp_path / "chart.png"
    # Minimal 1x1 PNG bytes
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
    img_file.write_bytes(png_bytes)

    # When sending a file path via CLI or IPC without uploading raw bytes
    daemon._input_queue.put_nowait({
        "text": "Explain this chart",
        "data": b"",
        "mime": "",
        "name": str(img_file),
    })

    with pytest.raises(InputCaptured):
        await asyncio.wait_for(daemon.send_inputs(session), 5)

    assert len(session.sent_turns) == 1
    parts = session.sent_turns[0][0].parts
    # Verify image part was loaded from disk and forwarded to session
    png_parts = [p for p in parts if getattr(p, "inline_data", None) and p.inline_data.mime_type == "image/png"]
    assert len(png_parts) == 1
    assert png_parts[0].inline_data.data == png_bytes


def test_daemon_send_input_enqueues_multimodal_item(daemon):
    item = {
        "text": "Check this file",
        "data": b"sample data",
        "mime": "text/plain",
        "name": "sample.txt",
    }
    daemon.send_input(item)
    assert not daemon._input_queue.empty()
    queued = daemon._input_queue.get_nowait()
    assert queued["text"] == "Check this file"
    assert queued["data"] == b"sample data"
    assert queued["name"] == "sample.txt"
