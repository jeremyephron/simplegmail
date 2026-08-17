from unittest.mock import MagicMock, patch

import pytest

from simplegmail.gmail import Gmail


def build_gmail():
    gmail = Gmail.__new__(Gmail)
    gmail.creds = MagicMock()
    return gmail


def build_worker(workers, build_message):
    worker = MagicMock()
    worker._build_message_from_ref.side_effect = build_message
    workers.append(worker)
    return worker


def test_parallel_retrieval_preserves_order_and_closes_services():
    gmail = build_gmail()
    message_refs = [{'id': str(i)} for i in range(21)]
    workers = []

    def build_message(user_id, message_ref, attachments):
        return message_ref['id']

    with patch(
        'simplegmail.gmail.Gmail',
        side_effect=lambda **_: build_worker(workers, build_message),
    ) as gmail_class:
        messages = Gmail._get_messages_from_refs(
            gmail, 'me', message_refs, attachments='ignore'
        )

    assert messages == [ref['id'] for ref in message_refs]
    assert gmail_class.call_count == 3
    assert all(worker.service.close.call_count == 1 for worker in workers)


def test_parallel_retrieval_propagates_worker_errors_and_closes_services():
    gmail = build_gmail()
    message_refs = [{'id': str(i)} for i in range(11)]
    workers = []
    error = RuntimeError('download failed')

    def build_message(user_id, message_ref, attachments):
        if message_ref['id'] == '6':
            raise error
        return message_ref['id']

    with patch(
        'simplegmail.gmail.Gmail',
        side_effect=lambda **_: build_worker(workers, build_message),
    ):
        with pytest.raises(RuntimeError) as raised:
            Gmail._get_messages_from_refs(gmail, 'me', message_refs)

    assert raised.value is error
    assert len(workers) == 2
    assert all(worker.service.close.call_count == 1 for worker in workers)
