"""Bounded filesystem operations exposed to the voice skill registry with full autonomy."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime
from urllib.parse import quote

CRITICAL_PATHS = {
    Path('/'),
    Path.home(),
    Path('/bin'),
    Path('/boot'),
    Path('/dev'),
    Path('/etc'),
    Path('/home'),
    Path('/lib'),
    Path('/lib64'),
    Path('/opt'),
    Path('/proc'),
    Path('/root'),
    Path('/sbin'),
    Path('/sys'),
    Path('/usr'),
    Path('/var'),
}


class FileOperationError(ValueError):
    pass


VERIFY_MAX_BYTES = 8 * 1024 * 1024
OFFICE_MAX_MEMBER_BYTES = 50 * 1024 * 1024


def _classify_mode(mode: int) -> str:
    """Return a human-readable filesystem entry type from an st_mode bitmask."""
    if stat.S_ISLNK(mode):
        return 'symlink'
    if stat.S_ISDIR(mode):
        return 'directory'
    if stat.S_ISREG(mode):
        return 'file'
    if stat.S_ISFIFO(mode):
        return 'fifo'
    if stat.S_ISSOCK(mode):
        return 'socket'
    if stat.S_ISCHR(mode):
        return 'char_device'
    if stat.S_ISBLK(mode):
        return 'block_device'
    return 'special'


def _open_regular_nonblocking(path: Path, *, follow_symlinks: bool = False) -> int:
    """Open a regular file without blocking on FIFOs or device nodes."""
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
    if not follow_symlinks:
        flags |= getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise FileOperationError(f'path is not a regular file: {path}')
    except Exception:
        os.close(fd)
        raise
    return fd


def _content_snapshot(path: Path) -> bytes | None:
    """Bound verification memory and do not follow symbolic links."""
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > VERIFY_MAX_BYTES:
            return None
        fd = _open_regular_nonblocking(path, follow_symlinks=False)
        with os.fdopen(fd, 'rb') as stream:
            value = stream.read(VERIFY_MAX_BYTES + 1)
        return value if len(value) <= VERIFY_MAX_BYTES else None
    except (OSError, FileOperationError):
        return None


def _content_result(result: dict, path: Path, expected: bytes | None,
                    *, offset: int = 0, absent: Path | None = None) -> dict:
    verified = False
    try:
        if expected is not None:
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                fd = _open_regular_nonblocking(path, follow_symlinks=False)
                with os.fdopen(fd, 'rb') as stream:
                    stream.seek(offset)
                    verified = stream.read(len(expected) + 1) == expected
            if absent is not None and (absent.exists() or absent.is_symlink()):
                verified = False
    except (OSError, FileOperationError):
        pass
    evidence = {'source': 'filesystem_readback', 'path': str(path), 'offset': offset,
                'observed_at': datetime.now().astimezone().isoformat(timespec='milliseconds')}
    if verified:
        evidence.update(bytes=len(expected), sha256=hashlib.sha256(expected).hexdigest())
    return {**result, 'verified': verified, 'evidence': evidence,
            **({} if verified else {'operation': result['status'], 'status': 'unverified',
                'reason': 'Content/source readback failed or exceeds the regular-file verification limit; do not repeat automatically.'})}


def path_for(value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > 4096:
        raise FileOperationError('invalid file path')
    import re
    clean = re.sub(r'^/home/[^/]+', str(Path.home()), value.strip())
    return Path(clean).expanduser().absolute()


def _target_path(path: Path) -> Path:
    # Resolve parent aliases while keeping a final symlink as the operated-on entry.
    if path.name in {'.', '..'}:
        return path.resolve()
    return path.parent.resolve() / path.name


def _is_critical(path: Path) -> bool:
    target = _target_path(path)
    return target == Path('/') or any(target == _target_path(critical) for critical in CRITICAL_PATHS)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _replace_path(source: Path, destination: Path) -> dict | None:
    """Install source at destination and keep an overwritten entry recoverable on failure."""
    backup = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.bak')
    had_destination = destination.exists() or destination.is_symlink()
    if had_destination:
        destination.rename(backup)
    try:
        source.rename(destination)
    except OSError as error:
        if destination.exists() or destination.is_symlink():
            if had_destination:
                raise OSError(f'{error}; replacement entry was preserved and the previous destination remains at {backup}') from error
            raise
        if had_destination:
            try:
                backup.rename(destination)
            except OSError as restore_error:
                raise OSError(f'{error}; could not restore the previous destination, which remains at {backup}: {restore_error}') from error
        raise
    if had_destination:
        try:
            _remove_path(backup)
        except OSError as error:
            return {'backup_path': str(backup), 'cleanup_error': str(error)}
    return None


def details(path: Path) -> dict:
    try:
        info = path.lstat()
    except OSError as error:
        raise FileOperationError(f'cannot inspect {path}: {error.strerror}') from None
    kind = _classify_mode(info.st_mode)
    return {
        'path': str(path),
        'name': path.name,
        'type': kind,
        'size': info.st_size,
        'mode': oct(info.st_mode & 0o777),
        'modified': datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds'),
    }


def inspect_path(value: str) -> dict:
    path = path_for(value)
    if not path.exists() and not path.is_symlink():
        return {'exists': False, 'path': str(path)}
    item = details(path)
    item['exists'] = True
    item['is_readable'] = os.access(path, os.R_OK)
    item['is_writable'] = os.access(path, os.W_OK)
    if item['type'] == 'file' and item['size'] <= 1024 * 1024:
        try:
            fd = _open_regular_nonblocking(path, follow_symlinks=False)
            with os.fdopen(fd, 'r', encoding='utf-8', errors='ignore') as stream:
                item['line_count'] = sum(1 for _ in stream)
        except Exception:
            pass
    return item


def list_directory(value: str, limit: int = 100, include_hidden: bool = True) -> dict:
    path = path_for(value)
    if not path.is_dir():
        raise FileOperationError('path is not a directory')
    if not 1 <= limit <= 500:
        raise FileOperationError('limit must be from 1 to 500')
    try:
        entries = [p for p in path.iterdir() if include_hidden or not p.name.startswith('.')]
        entries.sort(key=lambda item: (not item.is_dir(), item.name.casefold()))
        return {
            'path': str(path),
            'entries': [details(item) for item in entries[:limit]],
            'count': len(entries),
            'truncated': len(entries) > limit,
        }
    except OSError as error:
        raise FileOperationError(f'cannot list directory: {error.strerror}') from None


def _python_extract_pdf_stream_text(data: bytes) -> str:
    """Extract text from PDF stream objects in pure Python without external dependencies."""
    texts = []
    for match in re.finditer(rb'stream[\r\n]+(.*?)[\r\n]+endstream', data, re.DOTALL):
        chunk = match.group(1)
        try:
            decompressed = zlib.decompress(chunk)
        except Exception:
            decompressed = chunk
        for bt in re.finditer(rb'BT(.*?)ET', decompressed, re.DOTALL):
            for tj in re.finditer(rb'\((.*?)\)\s*Tj', bt.group(1)):
                try:
                    t = tj.group(1).decode('utf-8', errors='ignore')
                    if t.strip():
                        texts.append(t)
                except Exception:
                    pass
            for tj in re.finditer(rb'\[(.*?)\]\s*TJ', bt.group(1)):
                for sub in re.finditer(rb'\((.*?)\)', tj.group(1)):
                    try:
                        t = sub.group(1).decode('utf-8', errors='ignore')
                        if t.strip():
                            texts.append(t)
                    except Exception:
                        pass
    if not texts and (b'stream' in data or b'BT' in data):
        raw_strings = re.findall(rb'[a-zA-Z0-9.,;:!? \'\"]{4,}', data)
        pdf_syntax = {b'Catalog', b'Pages', b'Font', b'Type', b'Helvetica', b'Length', b'Resources', b'MediaBox', b'endobj', b'startxref', b'Obj', b'obj'}
        filtered = [s.decode('ascii', errors='ignore') for s in raw_strings if not any(kw in s for kw in pdf_syntax)]
        if filtered:
            texts.extend(filtered[:100])
    return '\n'.join(texts).strip()


def _extract_pdf_text(path: Path) -> tuple[str, int]:
    """Extract text from PDF via pdftotext, OCR (pdftoppm+tesseract), or stream fallback."""
    file_size = path.stat().st_size
    name = path.name
    pdftotext_bin = shutil.which('pdftotext')
    pdf_text = ""

    if pdftotext_bin:
        try:
            proc = subprocess.run(
                [pdftotext_bin, '-enc', 'UTF-8', '-layout', str(path), '-'],
                capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0 and proc.stdout.strip():
                pdf_text = proc.stdout.strip()
        except Exception:
            pass

        if not pdf_text:
            try:
                proc = subprocess.run(
                    [pdftotext_bin, '-enc', 'UTF-8', str(path), '-'],
                    capture_output=True, text=True, timeout=15
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    pdf_text = proc.stdout.strip()
            except Exception:
                pass

    if not pdf_text:
        pdftoppm_bin = shutil.which('pdftoppm')
        tesseract_bin = shutil.which('tesseract')
        if pdftoppm_bin and tesseract_bin:
            try:
                import tempfile
                with tempfile.TemporaryDirectory() as td:
                    prefix = str(Path(td) / 'p')
                    ppm = subprocess.run(
                        [pdftoppm_bin, '-png', '-r', '150', '-f', '1', '-l', '5', str(path), prefix],
                        capture_output=True, timeout=20
                    )
                    if ppm.returncode == 0:
                        ocr_pages = []
                        for idx, pfile in enumerate(sorted(Path(td).glob('p*.png')), start=1):
                            t_proc = subprocess.run(
                                [tesseract_bin, str(pfile), 'stdout'],
                                capture_output=True, text=True, timeout=10
                            )
                            if t_proc.returncode == 0 and t_proc.stdout.strip():
                                ocr_pages.append(f"--- Page {idx} (OCR) ---\n" + t_proc.stdout.strip())
                        if ocr_pages:
                            pdf_text = '\n\n'.join(ocr_pages)
            except Exception:
                pass

    if not pdf_text:
        try:
            raw_bytes = path.read_bytes()
            pdf_text = _python_extract_pdf_stream_text(raw_bytes)
        except Exception:
            pass

    if pdf_text:
        header = f"[PDF Document: {name} ({file_size:,} bytes)]\n"
        return header + pdf_text, file_size
    return f"[PDF Document: {name} ({file_size:,} bytes, scanned or image-based document with no selectable text)]", file_size


def _read_zip_member(zf: zipfile.ZipFile, member: str, max_bytes: int = OFFICE_MAX_MEMBER_BYTES) -> bytes:
    """Read a ZIP archive member after checking its uncompressed size."""
    info = zf.getinfo(member)
    if info.file_size > max_bytes:
        raise ValueError(
            f"ZIP member '{member}' uncompressed size ({info.file_size:,} bytes) "
            f"exceeds {max_bytes:,} byte limit"
        )
    with zf.open(info, 'r') as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(
            f"ZIP member '{member}' decompressed size exceeds {max_bytes:,} byte limit"
        )
    return data


def _xml_ns(elem: ET.Element) -> str:
    if elem.tag.startswith('{'):
        return elem.tag[:elem.tag.index('}') + 1]
    return ''


def _extract_xlsx_cells(zf: zipfile.ZipFile, shared_strings: list[str]) -> tuple[list[str], int]:
    """Extract cell text/numeric values from xl/worksheets/sheet*.xml."""
    sheet_files = sorted(
        n for n in zf.namelist()
        if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')
    )
    cells: list[str] = []
    for sfile in sheet_files:
        tree = ET.fromstring(_read_zip_member(zf, sfile))
        ns = _xml_ns(tree)
        for c in tree.iter(f'{ns}c'):
            cell_type = c.attrib.get('t', 'n')
            cell_ref = c.attrib.get('r', '')
            val = ''
            if cell_type == 'inlineStr':
                is_elem = c.find(f'{ns}is')
                if is_elem is not None:
                    val = ''.join(t.text for t in is_elem.iter(f'{ns}t') if t.text)
            else:
                v_elem = c.find(f'{ns}v')
                if v_elem is not None and v_elem.text is not None:
                    raw = v_elem.text
                    if cell_type == 's':
                        try:
                            idx = int(raw.strip())
                            val = shared_strings[idx] if 0 <= idx < len(shared_strings) else raw
                        except ValueError:
                            val = raw
                    elif cell_type == 'b':
                        val = 'TRUE' if raw.strip() == '1' else 'FALSE'
                    else:
                        val = raw
            if val:
                cells.append(f"{cell_ref}: {val}" if cell_ref else val)
    return cells, len(sheet_files)


def _extract_office_document(path: Path) -> tuple[str, int]:
    """Extract text from Word, PowerPoint, Excel, or OpenDocument formats."""
    file_size = path.stat().st_size
    ext = path.suffix.lower()
    name = path.name

    if ext == '.docx':
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                xml_data = _read_zip_member(zf, 'word/document.xml')
                tree = ET.fromstring(xml_data)
                paras = []
                for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                    if texts:
                        paras.append(''.join(texts))
                content = '\n\n'.join(paras)
                return f"[Word Document: {name} ({len(paras)} paragraphs)]\n\n{content}", file_size
        except Exception as err:
            return f"[Word Document: {name} (Error parsing DOCX: {err})]", file_size

    elif ext == '.pptx':
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                slide_files = sorted([n for n in zf.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')])
                slides = []
                for idx, sfile in enumerate(slide_files, start=1):
                    xml_data = _read_zip_member(zf, sfile)
                    tree = ET.fromstring(xml_data)
                    texts = [node.text for node in tree.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t') if node.text]
                    if texts:
                        slides.append(f"--- Slide {idx} ---\n" + '\n'.join(texts))
                content = '\n\n'.join(slides) if slides else "(No text on slides)"
                return f"[PowerPoint Presentation: {name} ({len(slide_files)} slides)]\n\n{content}", file_size
        except Exception as err:
            return f"[PowerPoint Presentation: {name} (Error parsing PPTX: {err})]", file_size

    elif ext == '.xlsx':
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                shared_strings = []
                if 'xl/sharedStrings.xml' in zf.namelist():
                    tree = ET.fromstring(_read_zip_member(zf, 'xl/sharedStrings.xml'))
                    ns = _xml_ns(tree)
                    for si in tree.iter(f'{ns}si'):
                        texts = [t.text for t in si.iter(f'{ns}t') if t.text]
                        shared_strings.append(''.join(texts))
                sheet_cells, sheet_count = _extract_xlsx_cells(zf, shared_strings)
                if sheet_cells:
                    content = f"[Excel Spreadsheet: {name} ({sheet_count} sheet(s), {len(sheet_cells)} cells)]"
                    content += "\nSample Cell Data:\n" + '\n'.join(sheet_cells[:200])
                elif shared_strings:
                    content = f"[Excel Spreadsheet: {name} ({len(shared_strings)} shared string cells)]"
                    content += "\nSample Cell Data:\n" + '\n'.join(shared_strings[:200])
                else:
                    content = f"[Excel Spreadsheet: {name} ({sheet_count} sheet(s), 0 cells)]"
                return content, file_size
        except Exception as err:
            return f"[Excel Spreadsheet: {name} (Error parsing XLSX: {err})]", file_size

    elif ext in ('.odt', '.ods', '.odp'):
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                tree = ET.fromstring(_read_zip_member(zf, 'content.xml'))
                texts = [node.text for node in tree.iter() if node.text and node.text.strip()]
                return f"[OpenDocument: {name}]\n\n" + '\n'.join(texts[:500]), file_size
        except Exception as err:
            return f"[OpenDocument: {name} (Error parsing: {err})]", file_size

    return f"[Document: {name}]", file_size


def _inspect_image(path: Path) -> tuple[str, int]:
    """Inspect image dimensions, format, color mode, EXIF metadata, and run OCR text extraction."""
    stat = path.stat()
    file_size = stat.st_size
    name = path.name
    ext = path.suffix.lower()

    dims = "unknown dimensions"
    img_type = ext.lstrip('.').upper()
    color_mode = ""
    exif_details = []

    # 1. Inspect dimensions & metadata via PIL (Pillow) if available
    try:
        from PIL import Image as PILImage, ExifTags
        with PILImage.open(path) as img:
            dims = f"{img.width}x{img.height}"
            img_type = img.format or img_type
            color_mode = f"mode: {img.mode}"
            if getattr(img, 'is_animated', False):
                n_f = getattr(img, 'n_frames', 1)
                color_mode += f", animated ({n_f} frames)"
            raw_exif = img.getexif()
            if raw_exif:
                interesting_tags = {
                    'Make': 'Camera Make',
                    'Model': 'Camera Model',
                    'DateTime': 'Date',
                    'DateTimeOriginal': 'Date Original',
                    'Software': 'Software',
                    'ExposureTime': 'Exposure',
                    'FNumber': 'F-Number',
                    'ISOSpeedRatings': 'ISO',
                    'Orientation': 'Orientation',
                }
                tag_map = {ExifTags.TAGS.get(k, k): v for k, v in raw_exif.items()}
                for k, label in interesting_tags.items():
                    if k in tag_map and tag_map[k]:
                        val = str(tag_map[k]).strip()
                        if val:
                            exif_details.append(f"{label}: {val}")
    except Exception:
        pass

    # 2. Fallback to ImageMagick identify
    if dims == "unknown dimensions":
        identify_bin = shutil.which('identify')
        if identify_bin:
            try:
                res = subprocess.run([identify_bin, '-format', '%m %wx%h', str(path)],
                                     capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split()
                    if len(parts) >= 2:
                        img_type, dims = parts[0], parts[1]
                    elif len(parts) == 1:
                        dims = parts[0]
            except Exception:
                pass

    # 3. OCR text extraction via tesseract
    ocr_text = ""
    tesseract_bin = shutil.which('tesseract')
    if tesseract_bin and file_size < 30 * 1024 * 1024:
        try:
            res = subprocess.run([tesseract_bin, str(path), 'stdout', '--oem', '1'],
                                 capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                ocr_text = res.stdout.strip()
        except Exception:
            pass

    details_parts = [x for x in [dims, f"format: {img_type}", color_mode] if x]
    details_str = ', '.join(details_parts) if details_parts else dims
    lines = [f"[Image File: {name} ({details_str}, size: {file_size:,} bytes)]"]
    if exif_details:
        lines.append("[EXIF Metadata]: " + ', '.join(exif_details[:8]))
    if ocr_text:
        lines.append("\n[Extracted Text (OCR)]:\n" + ocr_text)
    else:
        lines.append("(Visual image file; no text detected via OCR)")
    return '\n'.join(lines), file_size


def _inspect_video(path: Path) -> tuple[str, int]:
    """Inspect video file metadata, stream properties, subtitles, and key visual scenes."""
    stat = path.stat()
    file_size = stat.st_size
    name = path.name
    ext = path.suffix.lower()

    duration_str = "unknown"
    duration_secs = 0.0
    res_str = "unknown resolution"
    fps_str = ""
    vcodec = ""
    acodec = ""
    streams_summary = []
    subtitles_text = ""
    ocr_scenes = []

    ffprobe = shutil.which('ffprobe')
    ffmpeg = shutil.which('ffmpeg')
    tesseract = shutil.which('tesseract')

    if ffprobe:
        try:
            cmd = [
                ffprobe, '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(path)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout)
                fmt = data.get('format', {})
                try:
                    duration_secs = float(fmt.get('duration', 0))
                    if duration_secs > 0:
                        m, s = divmod(int(duration_secs), 60)
                        h, m = divmod(m, 60)
                        duration_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                except (ValueError, TypeError):
                    pass

                for s in data.get('streams', []):
                    c_type = s.get('codec_type')
                    c_name = s.get('codec_name', 'unknown')
                    if c_type == 'video' and not vcodec:
                        vcodec = c_name
                        w, h = s.get('width'), s.get('height')
                        if w and h:
                            res_str = f"{w}x{h}"
                        r_frame = s.get('r_frame_rate', '')
                        if '/' in r_frame:
                            try:
                                num, den = map(int, r_frame.split('/'))
                                if den > 0:
                                    fps_str = f"{round(num / den, 2)} fps"
                            except Exception:
                                pass
                        streams_summary.append(f"Video: {c_name.upper()} ({res_str}{', ' + fps_str if fps_str else ''})")
                    elif c_type == 'audio' and not acodec:
                        acodec = c_name
                        sr = s.get('sample_rate')
                        ch = s.get('channels')
                        sr_str = f"{int(sr)//1000} kHz" if sr and str(sr).isdigit() else ""
                        ch_str = f"{ch} ch" if ch else ""
                        audio_detail = ', '.join(x for x in [c_name.upper(), sr_str, ch_str] if x)
                        streams_summary.append(f"Audio: {audio_detail}")
                    elif c_type == 'subtitle':
                        lang = s.get('tags', {}).get('language', 'und')
                        streams_summary.append(f"Subtitles: {c_name} ({lang})")
        except Exception:
            pass

    # Extract embedded subtitles/dialogue transcript if available
    if ffmpeg:
        try:
            sub_proc = subprocess.run(
                [ffmpeg, '-y', '-i', str(path), '-map', '0:s:0', '-f', 'webvtt', 'pipe:1'],
                capture_output=True, text=True, timeout=8
            )
            if sub_proc.returncode == 0 and sub_proc.stdout.strip():
                raw_subs = sub_proc.stdout.splitlines()
                clean_lines = []
                for line in raw_subs:
                    line = line.strip()
                    if not line or line.startswith('WEBVTT') or '-->' in line or line.isdigit():
                        continue
                    if clean_lines and clean_lines[-1] == line:
                        continue
                    clean_lines.append(line)
                if clean_lines:
                    subtitles_text = '\n'.join(clean_lines[:200])
        except Exception:
            pass

    # Sample keyframes and run visual OCR extraction
    if ffmpeg and duration_secs > 0:
        try:
            timestamps = [
                max(0.1, duration_secs * 0.2),
                max(0.1, duration_secs * 0.5),
                max(0.1, duration_secs * 0.8),
            ]
            if duration_secs < 2:
                timestamps = [0.1]
            for idx, ts in enumerate(timestamps, start=1):
                ts_m, ts_s = divmod(int(ts), 60)
                ts_label = f"{ts_m:02d}:{ts_s:02d}"
                kf_cmd = [ffmpeg, '-ss', str(ts), '-i', str(path), '-vframes', '1',
                          '-f', 'image2', '-c:v', 'mjpeg', 'pipe:1']
                kf_proc = subprocess.run(kf_cmd, capture_output=True, timeout=5)
                if kf_proc.returncode == 0 and kf_proc.stdout:
                    kf_bytes = kf_proc.stdout
                    scene_ocr = ""
                    if tesseract:
                        try:
                            ocr_p = subprocess.run([tesseract, 'stdin', 'stdout', '--oem', '1'],
                                                   input=kf_bytes, capture_output=True, text=True, timeout=6)
                            if ocr_p.returncode == 0 and ocr_p.stdout.strip():
                                scene_ocr = ocr_p.stdout.strip()
                        except Exception:
                            pass
                    pct = int((ts / duration_secs) * 100) if duration_secs > 0 else 0
                    scene_desc = f"Scene {idx} at {ts_label} ({pct}%): sampled keyframe ({res_str})"
                    if scene_ocr:
                        scene_desc += f"\n  [Visual Text (OCR)]: {scene_ocr}"
                    ocr_scenes.append(scene_desc)
        except Exception:
            pass

    lines = [f"[Video File: {name} ({res_str}, duration: {duration_str}, size: {file_size:,} bytes)]"]
    if streams_summary:
        lines.append("[Streams]: " + ' | '.join(streams_summary))
    if subtitles_text:
        lines.append("\n[Dialogue / Subtitle Transcript]:\n" + subtitles_text)
    if ocr_scenes:
        lines.append("\n[Visual Scenes & Keyframes]:\n" + '\n'.join(ocr_scenes))
    elif not subtitles_text:
        lines.append("(Video media file analyzed; no embedded subtitles detected)")

    return '\n'.join(lines), file_size


def _inspect_audio(path: Path) -> tuple[str, int]:
    """Inspect audio file duration, sample rate, channels, codec, and tag metadata."""
    stat = path.stat()
    file_size = stat.st_size
    name = path.name
    ext = path.suffix.lower()

    duration_str = "unknown"
    codec = ext.lstrip('.').upper()
    channels_str = ""
    sample_rate_str = ""
    bitrate_str = ""
    tags_info = []

    ffprobe = shutil.which('ffprobe')
    if ffprobe:
        try:
            cmd = [
                ffprobe, '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(path)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout)
                fmt = data.get('format', {})
                try:
                    dur = float(fmt.get('duration', 0))
                    if dur > 0:
                        m, s = divmod(int(dur), 60)
                        h, m = divmod(m, 60)
                        duration_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                except (ValueError, TypeError):
                    pass

                bitrate = fmt.get('bit_rate')
                if bitrate and str(bitrate).isdigit():
                    bitrate_str = f"{int(bitrate)//1000} kbps"

                tags = fmt.get('tags', {})
                for k in ('title', 'artist', 'album', 'date', 'genre', 'track'):
                    val = tags.get(k) or tags.get(k.upper())
                    if val:
                        tags_info.append(f"{k.capitalize()}: {val}")

                for s in data.get('streams', []):
                    if s.get('codec_type') == 'audio':
                        codec = s.get('codec_name', codec).upper()
                        sr = s.get('sample_rate')
                        if sr and str(sr).isdigit():
                            sample_rate_str = f"{round(int(sr)/1000, 1)} kHz"
                        ch = s.get('channels')
                        ch_layout = s.get('channel_layout', '')
                        channels_str = f"{ch_layout or (str(ch) + ' ch')}"
                        break
        except Exception:
            pass

    details = [x for x in [duration_str, sample_rate_str, channels_str, codec, bitrate_str] if x and x != "unknown"]
    header = f"[Audio File: {name} ({', '.join(details)}, size: {file_size:,} bytes)]"
    lines = [header]
    if tags_info:
        lines.append("[Metadata Tags]: " + ', '.join(tags_info))
    return '\n'.join(lines), file_size


def _inspect_binary_or_archive(path: Path) -> tuple[str, int]:
    """Inspect archive contents or binary file metadata."""
    file_size = path.stat().st_size
    name = path.name
    ext = path.suffix.lower()

    if ext == '.zip':
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                infolist = zf.infolist()
                total_uncompressed = sum(i.file_size for i in infolist)
                lines = [f"[ZIP Archive: {name} ({len(infolist)} files, uncompressed: {total_uncompressed:,} bytes)]", "Files:"]
                for i in infolist[:100]:
                    lines.append(f"  {'[DIR] ' if i.is_dir() else '[FILE]'} {i.filename} ({i.file_size:,} bytes)")
                if len(infolist) > 100:
                    lines.append(f"  ... and {len(infolist) - 100} more files")
                return '\n'.join(lines), file_size
        except Exception:
            pass

    if ext in ('.tar', '.tgz', '.tar.gz', '.tar.bz2'):
        try:
            import tarfile
            with tarfile.open(path, 'r:*') as tf:
                members = tf.getmembers()
                lines = [f"[TAR Archive: {name} ({len(members)} entries)]", "Files:"]
                for m in members[:100]:
                    lines.append(f"  {'[DIR] ' if m.isdir() else '[FILE]'} {m.name} ({m.size:,} bytes)")
                if len(members) > 100:
                    lines.append(f"  ... and {len(members) - 100} more files")
                return '\n'.join(lines), file_size
        except Exception:
            pass

    file_bin = shutil.which('file')
    detected_type = "binary data"
    if file_bin:
        try:
            res = subprocess.run([file_bin, '-b', str(path)], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                detected_type = res.stdout.strip()
        except Exception:
            pass

    return f"[Binary File: {name} ({file_size:,} bytes, type: {detected_type})]", file_size


def _read_directory_structure(path: Path) -> tuple[str, int]:
    """Inspect directory contents, file sizes, and structure."""
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
    except OSError as err:
        raise FileOperationError(f'cannot list directory: {err.strerror}') from None

    total_files = 0
    total_dirs = 0
    total_bytes = 0

    lines = [f"[Directory: {path.resolve()}]"]
    entry_lines = []

    for item in entries:
        try:
            entry_stat = item.lstat()
            kind = _classify_mode(entry_stat.st_mode)
            if kind == 'symlink':
                target = os.readlink(item)
                entry_lines.append(f"  [LINK] {item.name} -> {target}")
            elif kind == 'directory':
                total_dirs += 1
                try:
                    child_count = sum(1 for _ in item.iterdir())
                    entry_lines.append(f"  [DIR]  {item.name}/ ({child_count} items)")
                except OSError:
                    entry_lines.append(f"  [DIR]  {item.name}/")
            elif kind == 'file':
                total_files += 1
                size = entry_stat.st_size
                total_bytes += size
                entry_lines.append(f"  [FILE] {item.name} ({size:,} bytes)")
            else:
                entry_lines.append(f"  [{kind.upper()[:4]}] {item.name}")
        except OSError:
            entry_lines.append(f"  [?]    {item.name}")

    summary = f"Total: {len(entries)} items ({total_dirs} directories, {total_files} files, {total_bytes:,} bytes)\n"
    lines.append(summary)
    lines.append("Contents:")
    lines.extend(entry_lines[:200])
    if len(entry_lines) > 200:
        lines.append(f"  ... and {len(entry_lines) - 200} more items")

    subdirs = [e for e in entries if e.is_dir() and not e.is_symlink() and not e.name.startswith('.')]
    if subdirs and len(subdirs) <= 10:
        lines.append("\nSubdirectory Previews:")
        for sub in subdirs[:6]:
            try:
                sub_children = sorted(sub.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))[:15]
                sub_names = [f"{c.name}/" if c.is_dir() else c.name for c in sub_children]
                lines.append(f"  {sub.name}/: {', '.join(sub_names) if sub_names else '(empty)'}")
            except OSError:
                pass

    return '\n'.join(lines), total_bytes


extract_pdf_text = _extract_pdf_text
extract_office_document = _extract_office_document
inspect_image = _inspect_image
inspect_binary_or_archive = _inspect_binary_or_archive
read_directory_structure = _read_directory_structure
python_extract_pdf_stream_text = _python_extract_pdf_stream_text


def read_text(value: str, offset: int = 0, max_chars: int = 20000) -> dict:
    path = path_for(value)
    if offset < 0:
        raise FileOperationError('offset must be nonnegative')
    if not 1 <= max_chars <= 100000:
        raise FileOperationError('max_chars must be from 1 to 100000')
    try:
        path.lstat()
    except OSError:
        raise FileOperationError(f'path does not exist: {path}') from None
    try:
        sinfo = path.stat()
    except OSError as error:
        raise FileOperationError(f'cannot inspect path {path}: {error.strerror}') from None

    # 1. Directory
    if stat.S_ISDIR(sinfo.st_mode):
        kind = 'directory'
        full_content, file_size = _read_directory_structure(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
            'is_directory': True,
        }

    # 2. Regular file only (reject FIFOs, sockets, device nodes, etc.)
    if not stat.S_ISREG(sinfo.st_mode):
        kind = _classify_mode(sinfo.st_mode)
        raise FileOperationError(f'cannot read non-regular file ({kind}): {path}')

    kind = 'file'
    file_size = sinfo.st_size
    ext = path.suffix.lower()

    if ext == '.pdf':
        kind = 'pdf'
        full_content, file_size = _extract_pdf_text(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    if ext in ('.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp'):
        kind = 'document'
        full_content, file_size = _extract_office_document(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.ico', '.avif', '.heic'):
        kind = 'image'
        full_content, file_size = _inspect_image(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    if ext in ('.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v', '.wmv', '.3gp', '.ts', '.mpeg', '.mpg'):
        kind = 'video'
        full_content, file_size = _inspect_video(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    if ext in ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.opus', '.wma'):
        kind = 'audio'
        full_content, file_size = _inspect_audio(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    if ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.7z'):
        kind = 'archive'
        full_content, file_size = _inspect_binary_or_archive(path)
        content_slice = full_content[offset:offset + max_chars]
        has_more = len(full_content) > offset + max_chars
        return {
            'path': str(path),
            'content': content_slice,
            'offset': offset,
            'chars_read': len(content_slice),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': kind,
        }

    try:
        fd = _open_regular_nonblocking(path, follow_symlinks=True)
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            remaining = offset
            while remaining > 0:
                skipped = stream.read(min(remaining, 8192))
                if not skipped:
                    break
                remaining -= len(skipped)
            content = stream.read(max_chars + 1)
        has_more = len(content) > max_chars
        return {
            'path': str(path),
            'content': content[:max_chars],
            'offset': offset,
            'chars_read': len(content[:max_chars]),
            'total_bytes': file_size,
            'truncated': has_more,
            'has_more': has_more,
            'type': 'text',
        }
    except UnicodeDecodeError:
        try:
            fd_sample = _open_regular_nonblocking(path, follow_symlinks=True)
            with os.fdopen(fd_sample, 'rb') as stream:
                raw_sample = stream.read(4096)
            if b'\x00' in raw_sample:
                kind = 'binary'
                full_content, file_size = _inspect_binary_or_archive(path)
            else:
                kind = 'text'
                fd_latin = _open_regular_nonblocking(path, follow_symlinks=True)
                with os.fdopen(fd_latin, 'r', encoding='latin-1', errors='replace') as stream:
                    full_content = stream.read()
            content_slice = full_content[offset:offset + max_chars]
            has_more = len(full_content) > offset + max_chars
            return {
                'path': str(path),
                'content': content_slice,
                'offset': offset,
                'chars_read': len(content_slice),
                'total_bytes': file_size,
                'truncated': has_more,
                'has_more': has_more,
                'type': kind,
            }
        except OSError as error:
            raise FileOperationError(f'cannot read file: {error}') from None
    except OSError as error:
        raise FileOperationError(f'cannot read text file: {error}') from None


def search_files(value: str, query: str, limit: int = 50, include_hidden: bool = False) -> dict:
    path = path_for(value)
    if not path.is_dir() or not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise FileOperationError('invalid directory or search query')
    if not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')
    matches = []
    inspected = 0
    for current, directories, files in os.walk(path, followlinks=False):
        if not include_hidden:
            directories[:] = [name for name in directories if not name.startswith('.')]
        for name in files + directories:
            if not include_hidden and name.startswith('.'):
                continue
            inspected += 1
            if inspected > 10000:
                return {'matches': matches, 'truncated': True}
            if query.casefold() in name.casefold():
                matches.append(str(Path(current) / name))
                if len(matches) >= limit:
                    return {'matches': matches, 'truncated': True}
    return {'matches': matches, 'truncated': False}


_RECENT_SKIP_DIRS = frozenset({
    '.git', '.hg', '.svn', 'node_modules', '__pycache__', '.venv', 'venv',
    '.mypy_cache', '.pytest_cache', '.ruff_cache', 'Trash',
})


def _resolve_recent_directory(value: str | None) -> Path:
    home = Path.home()
    if value is None or not str(value).strip():
        return home
    clean = str(value).strip()
    if '/' not in clean and '\\' not in clean and not clean.startswith(('~', '.')):
        aliases = {
            'home': home,
            'download': Path(os.getenv('XDG_DOWNLOAD_DIR') or home / 'Downloads'),
            'downloads': Path(os.getenv('XDG_DOWNLOAD_DIR') or home / 'Downloads'),
            'document': Path(os.getenv('XDG_DOCUMENTS_DIR') or home / 'Documents'),
            'documents': Path(os.getenv('XDG_DOCUMENTS_DIR') or home / 'Documents'),
            'docs': Path(os.getenv('XDG_DOCUMENTS_DIR') or home / 'Documents'),
            'desktop': Path(os.getenv('XDG_DESKTOP_DIR') or home / 'Desktop'),
            'picture': Path(os.getenv('XDG_PICTURES_DIR') or home / 'Pictures'),
            'pictures': Path(os.getenv('XDG_PICTURES_DIR') or home / 'Pictures'),
            'screenshots': Path(os.getenv('XDG_PICTURES_DIR') or home / 'Pictures') / 'Screenshots',
            'video': Path(os.getenv('XDG_VIDEOS_DIR') or home / 'Videos'),
            'videos': Path(os.getenv('XDG_VIDEOS_DIR') or home / 'Videos'),
            'music': Path(os.getenv('XDG_MUSIC_DIR') or home / 'Music'),
            'tmp': Path('/tmp'),
        }
        mapped = aliases.get(clean.casefold())
        if mapped is not None:
            return path_for(str(mapped))
    return path_for(clean)


def recent_files(
    value: str | None = None,
    extension: str | None = None,
    limit: int = 10,
    query: str | None = None,
    include_hidden: bool = False,
    max_depth: int = 4,
) -> dict:
    """Return recently modified regular files sorted newest-first."""
    base = _resolve_recent_directory(value)
    if not base.is_dir():
        raise FileOperationError(f'directory does not exist: {base}')
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or not 0 <= max_depth <= 10:
        raise FileOperationError('max_depth must be from 0 to 10')

    ext_filters: tuple[str, ...] = ()
    if extension is not None and str(extension).strip():
        normalized = []
        for token in str(extension).split(','):
            clean_ext = token.strip().lstrip('*.').lower()
            if clean_ext:
                normalized.append('.' + clean_ext)
        ext_filters = tuple(dict.fromkeys(normalized))

    clean_query = query.strip().casefold() if isinstance(query, str) and query.strip() else ''
    if clean_query and len(clean_query) > 200:
        raise FileOperationError('query is too long')

    entries: list[tuple[int, str, Path, os.stat_result]] = []
    inspected = 0
    truncated = False
    base_parts = len(base.parts)

    for current, directories, files in os.walk(base, followlinks=False):
        cur_path = Path(current)
        depth = len(cur_path.parts) - base_parts
        if depth >= max_depth:
            directories[:] = []
        elif not include_hidden:
            directories[:] = [
                d for d in directories
                if not d.startswith('.') and d not in _RECENT_SKIP_DIRS
            ]
        else:
            directories[:] = [d for d in directories if d not in _RECENT_SKIP_DIRS]

        for name in files:
            if not include_hidden and name.startswith('.'):
                continue
            inspected += 1
            if inspected > 25000:
                truncated = True
                break
            if ext_filters and Path(name).suffix.lower() not in ext_filters:
                continue
            if clean_query and clean_query not in name.casefold():
                continue
            candidate = cur_path / name
            try:
                info = candidate.stat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            entries.append((info.st_mtime_ns, name.casefold(), candidate, info))
        if truncated:
            break

    entries.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = entries[:limit]
    files_out = [
        {
            'path': str(file_path),
            'name': file_path.name,
            'extension': file_path.suffix.lower(),
            'size_bytes': info.st_size,
            'modified_ts': round(info.st_mtime, 3),
            'modified': datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds'),
        }
        for _, _, file_path, info in selected
    ]
    return {
        'status': 'ok',
        'directory': str(base),
        'extension': ext_filters[0] if len(ext_filters) == 1 else (','.join(ext_filters) if ext_filters else None),
        'query': clean_query or None,
        'latest': files_out[0] if files_out else None,
        'files': files_out,
        'count': len(files_out),
        'truncated': truncated,
    }


def search_file_content(value: str, query: str, limit: int = 30, max_file_size: int = 1024 * 1024) -> dict:
    path = path_for(value)
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise FileOperationError('invalid search query')
    if not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')

    try:
        path.lstat()
        sinfo = path.stat()
    except OSError:
        raise FileOperationError('path does not exist or is not searchable') from None

    matches = []
    files_to_search: list[tuple[Path, bool]] = []
    if stat.S_ISREG(sinfo.st_mode):
        files_to_search = [(path, True)]
    elif stat.S_ISDIR(sinfo.st_mode):
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if not f.startswith('.'):
                    files_to_search.append((Path(root) / f, False))
                    if len(files_to_search) >= 5000:
                        break
            if len(files_to_search) >= 5000:
                break
    else:
        raise FileOperationError('path does not exist or is not searchable')

    query_cf = query.casefold()
    for file_path, follow_links in files_to_search:
        try:
            info = file_path.stat() if follow_links else file_path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > max_file_size:
                continue
            fd = _open_regular_nonblocking(file_path, follow_symlinks=follow_links)
            with os.fdopen(fd, 'r', encoding='utf-8', errors='ignore') as stream:
                for line_idx, line in enumerate(stream, start=1):
                    if query_cf in line.casefold():
                        matches.append({
                            'path': str(file_path),
                            'line_number': line_idx,
                            'line': line.strip()[:200]
                        })
                        if len(matches) >= limit:
                            return {'query': query, 'matches': matches, 'truncated': True}
        except (OSError, FileOperationError):
            continue

    return {'query': query, 'matches': matches, 'truncated': False}


def write_text(value: str, content: str, overwrite: bool = False) -> dict:
    return _write_text(path_for(value), content, overwrite)


def _write_text(path: Path, content: str, overwrite: bool, *, expected: bytes | None = None) -> dict:
    if not isinstance(content, str) or len(content.encode('utf-8')) > 5 * 1024 * 1024:
        raise FileOperationError('content must be text of at most 5 MiB')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            if path.exists() and not path.is_file():
                raise FileOperationError('path is not a regular file')
            temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
            stream = temporary.open('x', encoding='utf-8')
            try:
                with stream:
                    stream.write(content)
                if overwrite:
                    if path.exists():
                        temporary.chmod(path.stat().st_mode & 0o777)
                    # shortcut: the directory lock only covers cooperating writers, use an OS-level conditional replace if available.
                    if expected is not None and _content_snapshot(path) != expected:
                        raise FileOperationError('file changed since it was read')
                    temporary.replace(path)
                else:
                    try:
                        os.link(temporary, path)
                    except FileExistsError:
                        raise FileOperationError('file exists; set overwrite to true to replace it') from None
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            os.close(directory)
    except OSError as error:
        raise FileOperationError(f'cannot write file: {error.strerror}') from None
    return _content_result({'status': 'written', 'path': str(path), 'bytes': len(content.encode('utf-8'))},
                           path, content.encode('utf-8'))


def append_text(value: str, content: str) -> dict:
    path = path_for(value)
    if not isinstance(content, str):
        raise FileOperationError('content must be text')
    encoded = content.encode('utf-8')
    if len(encoded) > 5 * 1024 * 1024:
        raise FileOperationError('content must be at most 5 MiB')
    if path.exists() and not path.is_file():
        raise FileOperationError('path is not a regular file')
    offset = path.stat().st_size if path.exists() else 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(content)
    except OSError as error:
        raise FileOperationError(f'cannot append to file: {error.strerror}') from None
    return _content_result({'status': 'appended', 'path': str(path), 'bytes_appended': len(encoded)},
                           path, encoded, offset=offset)


def make_directory(value: str) -> dict:
    path = path_for(value)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FileOperationError(f'cannot create directory: {error.strerror}') from None
    verified = path.is_dir()
    return {'status': 'created' if verified else 'unverified', 'path': str(path), 'verified': verified,
            'evidence': {'source': 'filesystem_readback', 'observed_at': datetime.now().astimezone().isoformat(),
                         'path': str(path), 'is_directory': verified}}


def move_path(source: str, destination: str, overwrite: bool = False) -> dict:
    src, dst = _target_path(path_for(source)), _target_path(path_for(destination))
    if _is_critical(src):
        raise FileOperationError('cannot move system root or home directory')
    if not src.exists() and not src.is_symlink():
        raise FileOperationError('source does not exist')
    if _is_critical(dst):
        raise FileOperationError('cannot overwrite system root or home directory')
    if src == dst or src in dst.parents or dst in src.parents:
        raise FileOperationError('cannot move a directory inside itself')
    expected = _content_snapshot(src)
    replacement_backup = None
    if dst.exists() or dst.is_symlink():
        if not overwrite:
            raise FileOperationError('destination already exists; set overwrite to true to replace it')
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() or dst.is_symlink():
            stage = dst.with_name('.' + dst.name + '.' + uuid.uuid4().hex + '.stage')
            shutil.move(str(src), str(stage))
            try:
                replacement_backup = _replace_path(stage, dst)
            except OSError:
                if stage.exists() or stage.is_symlink():
                    shutil.move(str(stage), str(src))
                raise
        else:
            shutil.move(str(src), str(dst))
    except OSError as error:
        raise FileOperationError(f'cannot move path: {error}') from None
    return _content_result({'status': 'moved', 'source': str(src), 'destination': str(dst),
                            **({'replacement_backup': replacement_backup} if replacement_backup else {})},
                           dst, expected, absent=src)


def copy_path(source: str, destination: str, overwrite: bool = False) -> dict:
    src, dst = _target_path(path_for(source)), _target_path(path_for(destination))
    if not src.exists() and not src.is_symlink():
        raise FileOperationError('source does not exist')
    if _is_critical(dst):
        raise FileOperationError('cannot overwrite system root or home directory')
    if src == dst or src in dst.parents or dst in src.parents:
        raise FileOperationError('cannot copy a directory inside itself')
    expected = _content_snapshot(src)
    replacement_backup = None
    if dst.exists() or dst.is_symlink():
        if not overwrite:
            raise FileOperationError('destination already exists; set overwrite to true to replace it')
    target = dst
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() or dst.is_symlink():
            target = dst.with_name('.' + dst.name + '.' + uuid.uuid4().hex + '.stage')
        if src.is_dir() and not src.is_symlink():
            shutil.copytree(src, target, symlinks=True)
        elif src.is_symlink():
            target.symlink_to(os.readlink(src))
        else:
            shutil.copy2(src, target)
        if target != dst:
            replacement_backup = _replace_path(target, dst)
    except OSError as error:
        if target != dst:
            try:
                _remove_path(target)
            except OSError:
                pass
        raise FileOperationError(f'cannot copy path: {error}') from None
    return _content_result({'status': 'copied', 'source': str(src), 'destination': str(dst),
                            **({'replacement_backup': replacement_backup} if replacement_backup else {})}, dst, expected)


def replace_text(value: str, old: str, new: str) -> dict:
    path = path_for(value)
    if not path.is_file() or not old or not isinstance(old, str) or not isinstance(new, str):
        raise FileOperationError('invalid text replacement')
    try:
        source = path.read_bytes()
        content = source.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    except (OSError, UnicodeError) as error:
        raise FileOperationError(f'cannot read text file: {error}') from None
    if len(content.encode('utf-8')) > 5 * 1024 * 1024:
        raise FileOperationError('file is too large for text replacement')
    count = content.count(old)
    if count != 1:
        raise FileOperationError(f'expected exactly one matching passage; found {count}')
    result = _write_text(path, content.replace(old, new, 1), overwrite=True, expected=source)
    return {**result, 'status': 'edited' if result.get('verified') else 'unverified'}


def trash_path(value: str) -> dict:
    path = _target_path(path_for(value))
    if _is_critical(path) or not (path.exists() or path.is_symlink()):
        raise FileOperationError('cannot trash this path')
    data_home = Path(os.getenv('XDG_DATA_HOME') or Path.home() / '.local/share')
    trash = data_home / 'Trash'
    name = path.name + '.' + uuid.uuid4().hex[:8]
    target = trash / 'files' / name
    info = trash / 'info' / (name + '.trashinfo')
    created_info = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        info.parent.mkdir(parents=True, exist_ok=True)
        with info.open('x', encoding='utf-8') as stream:
            created_info = True
            stream.write('[Trash Info]\nPath=' + quote(str(path), safe='/') +
                         '\nDeletionDate=' + datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '\n')
        shutil.move(str(path), str(target))
    except OSError as error:
        if target.exists() or target.is_symlink():
            raise FileOperationError(f'Trash operation failed; inspect the copy at {target}: {error}') from None
        if created_info:
            try:
                info.unlink(missing_ok=True)
            except OSError:
                raise FileOperationError(f'Trash operation failed; leftover metadata at {info}: {error}') from None
        raise FileOperationError(f'cannot move path to Trash: {error.strerror}') from None
    return {'status': 'trashed', 'original': str(path), 'trash_path': str(target)}


def delete_path(value: str, recursive: bool = False) -> dict:
    path = _target_path(path_for(value))
    if _is_critical(path):
        raise FileOperationError('cannot delete system root or home directory')
    if not path.exists() and not path.is_symlink():
        raise FileOperationError('path does not exist')
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            if not recursive and any(path.iterdir()):
                raise FileOperationError('directory is not empty; set recursive to true to delete it')
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as error:
        raise FileOperationError(f'cannot delete path: {error.strerror}') from None
    return {'status': 'deleted', 'path': str(path)}
