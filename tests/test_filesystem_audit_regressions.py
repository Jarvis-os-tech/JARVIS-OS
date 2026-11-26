import os
from pathlib import Path
import socket
import zipfile

import pytest

import filesystem.filesystem as files


@pytest.mark.parametrize('operation', ['delete', 'trash'])
def test_critical_path_aliases_are_rejected(tmp_path, monkeypatch, operation):
    protected = tmp_path / 'protected'
    protected.mkdir()
    (protected / 'child').mkdir()
    (protected / 'keep.txt').write_text('keep')
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})
    alias = tmp_path / 'parent-alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    escaped = str(alias / 'protected' / 'child' / '..')

    with pytest.raises(files.FileOperationError):
        getattr(files, f'{operation}_path')(escaped)
    assert (protected / 'keep.txt').read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_critical_destination_alias_is_rejected(tmp_path, monkeypatch, operation):
    protected = tmp_path / 'protected'
    protected.mkdir()
    (protected / 'child').mkdir()
    source = tmp_path / 'source.txt'
    source.write_text('keep')
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})
    destination = str(protected / 'child' / '..')

    with pytest.raises(files.FileOperationError, match='cannot overwrite'):
        getattr(files, f'{operation}_path')(str(source), destination, overwrite=True)
    assert source.read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_ancestor_destination_cannot_remove_source(tmp_path, operation):
    parent = tmp_path / 'parent'
    parent.mkdir()
    source = parent / 'source.txt'
    source.write_text('keep')

    with pytest.raises(files.FileOperationError, match='inside itself'):
        getattr(files, f'{operation}_path')(str(source), str(parent), overwrite=True)
    assert source.read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_ancestor_alias_destination_cannot_remove_source(tmp_path, operation):
    real = tmp_path / 'real'
    parent = real / 'parent'
    parent.mkdir(parents=True)
    source = parent / 'child.txt'
    source.write_text('keep')
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(files.FileOperationError, match='inside itself'):
        getattr(files, f'{operation}_path')(str(source), str(alias / 'parent'), overwrite=True)
    assert source.read_text() == 'keep'


def test_move_rejects_protected_source_alias(tmp_path, monkeypatch):
    protected = tmp_path / 'protected'
    (protected / 'child').mkdir(parents=True)
    alias = tmp_path / 'alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})

    with pytest.raises(files.FileOperationError, match='cannot move system root or home'):
        files.move_path(str(alias / 'protected' / 'child' / '..'), str(tmp_path / 'destination'))
    assert protected.is_dir()


def test_delete_symlink_keeps_its_target(tmp_path):
    target = tmp_path / 'target.txt'
    target.write_text('keep')
    link = tmp_path / 'link.txt'
    link.symlink_to(target)

    assert files.delete_path(str(link))['status'] == 'deleted'
    assert not link.is_symlink()
    assert target.read_text() == 'keep'


def test_copy_overwrite_failure_keeps_destination(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')

    def fail_copy(src, dst, *args, **kwargs):
        Path(dst).write_text('partial')
        raise OSError('simulated copy failure')

    monkeypatch.setattr(files.shutil, 'copy2', fail_copy)
    with pytest.raises(files.FileOperationError, match='cannot copy path'):
        files.copy_path(str(source), str(destination), overwrite=True)
    assert destination.read_text() == 'old'
    assert not list(tmp_path.glob('*.stage'))


def test_move_overwrite_failure_restores_destination_and_source(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')

    def fail_replace(stage, target):
        raise OSError('simulated install failure')

    monkeypatch.setattr(files, '_replace_path', fail_replace)
    with pytest.raises(files.FileOperationError, match='cannot move path'):
        files.move_path(str(source), str(destination), overwrite=True)
    assert source.read_text() == 'new'
    assert destination.read_text() == 'old'


def test_failed_install_restores_destination(tmp_path, monkeypatch):
    staged = tmp_path / '.destination.stage'
    destination = tmp_path / 'destination'
    staged.write_text('new')
    destination.write_text('old')
    original_rename = Path.rename

    def fail_staged_rename(path, target):
        if path == staged:
            raise OSError('simulated install failure')
        return original_rename(path, target)

    monkeypatch.setattr(Path, 'rename', fail_staged_rename)
    with pytest.raises(OSError, match='simulated install failure'):
        files._replace_path(staged, destination)
    assert destination.read_text() == 'old'
    assert staged.read_text() == 'new'


def test_failed_install_does_not_delete_concurrent_destination(tmp_path, monkeypatch):
    staged = tmp_path / '.destination.stage'
    destination = tmp_path / 'destination'
    staged.write_text('new')
    destination.write_text('old')
    original_rename = Path.rename

    def race_staged_rename(path, target):
        if path == staged:
            destination.write_text('concurrent')
            raise OSError('simulated install failure')
        return original_rename(path, target)

    monkeypatch.setattr(Path, 'rename', race_staged_rename)
    with pytest.raises(OSError, match='previous destination remains at'):
        files._replace_path(staged, destination)
    backups = list(tmp_path.glob('.*.bak'))
    assert destination.read_text() == 'concurrent'
    assert len(backups) == 1 and backups[0].read_text() == 'old'


def test_copy_reports_backup_when_cleanup_fails(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')
    original_remove = files._remove_path

    def fail_backup_cleanup(path):
        if path.name.endswith('.bak'):
            raise OSError('simulated cleanup failure')
        original_remove(path)

    monkeypatch.setattr(files, '_remove_path', fail_backup_cleanup)
    result = files.copy_path(str(source), str(destination), overwrite=True)
    assert result['status'] == 'copied'
    backup = Path(result['replacement_backup']['backup_path'])
    assert result['replacement_backup']['cleanup_error'] == 'simulated cleanup failure'
    assert destination.read_text() == 'new'
    assert backup.read_text() == 'old'


def test_non_regular_files_are_classified_and_rejected_without_hanging(tmp_path):
    fifo = tmp_path / 'pipe.fifo'
    os.mkfifo(fifo)
    fifo_link = tmp_path / 'pipe-link'
    fifo_link.symlink_to(fifo)
    regular = tmp_path / 'note.txt'
    regular.write_text('needle in regular file\n', encoding='utf-8')

    sock_path = tmp_path / 'test.sock'
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        srv.bind(str(sock_path))

        assert files.details(fifo)['type'] == 'fifo'
        assert files.details(sock_path)['type'] == 'socket'
        assert files.inspect_path(str(fifo))['type'] == 'fifo'
        assert files._content_snapshot(fifo) is None

        with pytest.raises(files.FileOperationError, match='non-regular file'):
            files.read_text(str(fifo))
        with pytest.raises(files.FileOperationError, match='non-regular file'):
            files.read_text(str(fifo_link))
        with pytest.raises(files.FileOperationError, match='non-regular file'):
            files.read_text(str(sock_path))

        with pytest.raises(files.FileOperationError, match='not searchable'):
            files.search_file_content(str(fifo), 'needle')

        search_res = files.search_file_content(str(tmp_path), 'needle')
        assert len(search_res['matches']) == 1
        assert search_res['matches'][0]['path'] == str(regular)
    finally:
        srv.close()


@pytest.mark.parametrize('critical', ['/home', '/var', '/opt'])
def test_system_parent_directories_are_critical(critical):
    assert Path(critical) in files.CRITICAL_PATHS
    with pytest.raises(files.FileOperationError, match='cannot delete system root or home'):
        files.delete_path(critical, recursive=True)
    with pytest.raises(files.FileOperationError, match='cannot trash this path'):
        files.trash_path(critical)
    with pytest.raises(files.FileOperationError, match='cannot move system root or home'):
        files.move_path(critical, '/tmp/should-never-happen')


def test_office_zip_member_size_guard_blocks_oversized_member(tmp_path):
    bomb_docx = tmp_path / 'bomb.docx'
    oversized_bytes = b'0' * (files.OFFICE_MAX_MEMBER_BYTES + 1024)
    with zipfile.ZipFile(bomb_docx, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('word/document.xml', oversized_bytes)

    res = files.read_text(str(bomb_docx))
    assert res['type'] == 'document'
    assert 'Error parsing DOCX' in res['content']
    assert 'exceeds' in res['content']


def test_xlsx_extracts_numeric_and_inline_string_cells_without_shared_strings(tmp_path):
    xlsx_path = tmp_path / 'inline_and_nums.xlsx'
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1">
          <c r="A1" t="inlineStr"><is><t>Revenue</t></is></c>
          <c r="B1"><v>42500</v></c>
          <c r="C1" t="b"><v>1</v></c>
        </row>
      </sheetData>
    </worksheet>"""
    with zipfile.ZipFile(xlsx_path, 'w') as zf:
        zf.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    res = files.read_text(str(xlsx_path))
    assert res['type'] == 'document'
    assert 'Revenue' in res['content']
    assert '42500' in res['content']
    assert 'TRUE' in res['content']

    # Also verify when xl/sharedStrings.xml exists but is empty.
    xlsx_empty_ss = tmp_path / 'empty_ss.xlsx'
    empty_ss = '<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
    with zipfile.ZipFile(xlsx_empty_ss, 'w') as zf:
        zf.writestr('xl/sharedStrings.xml', empty_ss)
        zf.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    res2 = files.read_text(str(xlsx_empty_ss))
    assert 'Revenue' in res2['content']
    assert '42500' in res2['content']
