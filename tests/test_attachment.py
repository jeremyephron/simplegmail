from unittest.mock import MagicMock

import pytest

from simplegmail.attachment import Attachment


def build_attachment(filename='attachment.txt', data=b'attachment data'):
    return Attachment(
        service=MagicMock(),
        user_id='me',
        msg_id='message-id',
        att_id='attachment-id',
        filename=filename,
        filetype='text/plain',
        data=data,
    )


def test_save_accepts_existing_directory(tmp_path):
    destination = tmp_path / 'downloads'
    destination.mkdir()

    build_attachment().save(filepath=str(destination))

    assert (destination / 'attachment.txt').read_bytes() == b'attachment data'


def test_save_preserves_full_filepath_behavior(tmp_path):
    destination = tmp_path / 'renamed.txt'

    build_attachment().save(filepath=str(destination))

    assert destination.read_bytes() == b'attachment data'


def test_save_uses_filename_basename_with_directory(tmp_path):
    destination = tmp_path / 'downloads'
    destination.mkdir()

    build_attachment(filename='../attachment.txt').save(
        filepath=str(destination)
    )

    assert (destination / 'attachment.txt').read_bytes() == b'attachment data'
    assert not (tmp_path / 'attachment.txt').exists()


def test_save_directory_respects_overwrite_option(tmp_path):
    destination = tmp_path / 'downloads'
    destination.mkdir()
    saved_attachment = destination / 'attachment.txt'
    saved_attachment.write_bytes(b'existing data')
    attachment = build_attachment()

    with pytest.raises(FileExistsError):
        attachment.save(filepath=str(destination))

    assert saved_attachment.read_bytes() == b'existing data'

    attachment.save(filepath=str(destination), overwrite=True)

    assert saved_attachment.read_bytes() == b'attachment data'
