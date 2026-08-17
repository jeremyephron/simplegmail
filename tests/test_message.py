from unittest.mock import MagicMock, patch

import pytest

from simplegmail import label
from simplegmail.message import Message


def build_message(response):
    service = MagicMock()
    modify = service.users.return_value.messages.return_value.modify
    modify.return_value.execute.return_value = response

    message = Message(
        service=service,
        creds=MagicMock(),
        user_id='me',
        msg_id='message-id',
        thread_id='thread-id',
        recipient='recipient@example.com',
        sender='sender@example.com',
        subject='subject',
        date='date',
        snippet='snippet',
        label_ids=[label.INBOX],
    )
    return message, modify


def test_archive_handles_response_without_label_ids():
    message, modify = build_message({})

    message.archive()

    assert message.label_ids == []
    modify.assert_called_once_with(
        userId='me',
        id='message-id',
        body={'addLabelIds': [], 'removeLabelIds': ['INBOX']},
    )


def test_modify_labels_uses_returned_label_ids():
    message, _ = build_message({'labelIds': ['STARRED']})

    message.modify_labels(label.STARRED, label.INBOX)

    assert message.label_ids == ['STARRED']


def test_missing_label_ids_does_not_hide_failed_addition():
    message, _ = build_message({})

    with pytest.raises(
        AssertionError,
        match='An error occurred while modifying message label.',
    ):
        message.star()

    assert message.label_ids == [label.INBOX]


def test_service_refreshes_expired_credentials():
    message, _ = build_message({})
    message.creds.expired = True
    request = MagicMock()

    with patch('simplegmail.message.Request', return_value=request):
        service = message.service

    assert service is message._service
    message.creds.refresh.assert_called_once_with(request)
