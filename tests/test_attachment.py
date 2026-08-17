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
    attachment.data = None
    attachment.download = MagicMock()

    with pytest.raises(FileExistsError):
        attachment.save(filepath=str(destination))

    assert saved_attachment.read_bytes() == b'existing data'
    attachment.download.assert_not_called()

    attachment.download.side_effect = lambda: setattr(
        attachment, 'data', b'attachment data'
    )
    attachment.save(filepath=str(destination), overwrite=True)

    assert saved_attachment.read_bytes() == b'attachment data'


def test_download_decodes_unpadded_base64url_once():
    attachment = build_attachment(data=None)
    get = attachment._service.users.return_value.messages.return_value \
        .attachments.return_value.get
    get.return_value.execute.return_value = {'data': '_w'}

    attachment.download()
    attachment.download()

    assert attachment.data == b'\xff'
    get.assert_called_once_with(
        userId='me', messageId='message-id', id='attachment-id'
    )


def test_save_uses_stored_filename_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    build_attachment().save()

    assert (tmp_path / 'attachment.txt').read_bytes() == b'attachment data'
