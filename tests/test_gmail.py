import base64
import json
from unittest.mock import MagicMock, call, patch

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


def build_credentials(valid=True, expired=False, refresh_token='refresh'):
    creds = MagicMock()
    creds.valid = valid
    creds.expired = expired
    creds.refresh_token = refresh_token
    creds.to_json.return_value = '{"token": "saved"}'
    return creds


def test_uses_injected_credentials_without_loading_token_file():
    creds = build_credentials()
    service = MagicMock()

    with patch('simplegmail.gmail.build', return_value=service) as build:
        gmail = Gmail(_creds=creds)

    assert gmail.creds is creds
    assert gmail.service is service
    build.assert_called_once_with(
        'gmail', 'v1', credentials=creds, cache_discovery=False
    )


def test_loads_valid_stored_credentials(tmp_path):
    token_file = tmp_path / 'token.json'
    token_file.write_text('{}')
    creds = build_credentials()

    with patch(
        'simplegmail.gmail.Credentials.from_authorized_user_file',
        return_value=creds,
    ) as load:
        with patch(
            'simplegmail.gmail.InstalledAppFlow.from_client_secrets_file'
        ) as start_flow:
            with patch('simplegmail.gmail.build'):
                gmail = Gmail(creds_file=str(token_file))

    assert gmail.creds is creds
    load.assert_called_once_with(str(token_file), Gmail._SCOPES)
    start_flow.assert_not_called()
    assert token_file.read_text() == '{}'


def test_refreshes_and_saves_expired_credentials(tmp_path):
    token_file = tmp_path / 'token.json'
    token_file.write_text('{}')
    creds = build_credentials(valid=False, expired=True)
    request = MagicMock()

    with patch(
        'simplegmail.gmail.Credentials.from_authorized_user_file',
        return_value=creds,
    ):
        with patch('simplegmail.gmail.Request', return_value=request):
            with patch('simplegmail.gmail.build'):
                Gmail(creds_file=str(token_file))

    creds.refresh.assert_called_once_with(request)
    assert token_file.read_text() == creds.to_json.return_value


@pytest.mark.parametrize(
    ('noauth_local_webserver', 'open_browser'),
    [(False, True), (True, False)],
)
def test_authorizes_and_saves_new_credentials(
    tmp_path, noauth_local_webserver, open_browser
):
    token_file = tmp_path / f'token-{open_browser}.json'
    secret_file = tmp_path / 'client-secret.json'
    creds = build_credentials()
    flow = MagicMock()
    flow.run_local_server.return_value = creds

    with patch(
        'simplegmail.gmail.InstalledAppFlow.from_client_secrets_file',
        return_value=flow,
    ) as start_flow:
        with patch('simplegmail.gmail.build'):
            gmail = Gmail(
                client_secret_file=str(secret_file),
                creds_file=str(token_file),
                access_type='online',
                noauth_local_webserver=noauth_local_webserver,
            )

    assert gmail.creds is creds
    start_flow.assert_called_once_with(str(secret_file), Gmail._SCOPES)
    flow.run_local_server.assert_called_once_with(
        port=8080,
        open_browser=open_browser,
        access_type='online',
        prompt='consent',
    )
    assert token_file.read_text() == creds.to_json.return_value


def test_reauthorizes_when_stored_credentials_are_invalid(tmp_path):
    token_file = tmp_path / 'token.json'
    token_file.write_text('invalid')
    creds = build_credentials()
    flow = MagicMock()
    flow.run_local_server.return_value = creds

    with patch(
        'simplegmail.gmail.Credentials.from_authorized_user_file',
        side_effect=ValueError,
    ):
        with patch(
            'simplegmail.gmail.InstalledAppFlow.from_client_secrets_file',
            return_value=flow,
        ):
            with patch('simplegmail.gmail.build'):
                Gmail(creds_file=str(token_file))

    assert token_file.read_text() == creds.to_json.return_value


def test_authorization_uses_an_available_callback_port():
    creds = build_credentials()
    flow = MagicMock()
    flow.run_local_server.side_effect = [OSError, OSError, creds]

    result = Gmail._run_auth_flow(flow, 'offline', False)

    assert result is creds
    assert flow.run_local_server.call_args_list == [
        call(
            port=8080,
            open_browser=True,
            access_type='offline',
            prompt='consent',
        ),
        call(
            port=8090,
            open_browser=True,
            access_type='offline',
            prompt='consent',
        ),
        call(
            port=0,
            open_browser=True,
            access_type='offline',
            prompt='consent',
        ),
    ]


def test_reuses_legacy_oauth2client_token(tmp_path):
    token_file = tmp_path / 'token.json'
    token_file.write_text(json.dumps({
        'access_token': 'legacy-access-token',
        'client_id': 'client-id',
        'client_secret': 'client-secret',
        'refresh_token': 'refresh-token',
        'token_expiry': '2020-01-01T00:00:00Z',
        'token_uri': 'https://oauth2.googleapis.com/token',
        '_class': 'OAuth2Credentials',
        '_module': 'oauth2client.client',
    }))

    with patch(
        'simplegmail.gmail.InstalledAppFlow.from_client_secrets_file'
    ) as start_flow:
        with patch(
            'simplegmail.gmail.Credentials.refresh'
        ) as refresh:
            with patch('simplegmail.gmail.build'):
                gmail = Gmail(creds_file=str(token_file))

    assert gmail.creds.refresh_token == 'refresh-token'
    refresh.assert_called_once()
    start_flow.assert_not_called()
    assert json.loads(token_file.read_text())['refresh_token'] == 'refresh-token'


def test_missing_client_secret_has_clear_error(tmp_path):
    secret_file = tmp_path / 'missing-client-secret.json'

    with patch(
        'simplegmail.gmail.InstalledAppFlow.from_client_secrets_file',
        side_effect=FileNotFoundError,
    ):
        with pytest.raises(FileNotFoundError) as raised:
            Gmail(
                client_secret_file=str(secret_file),
                creds_file=str(tmp_path / 'token.json'),
            )

    assert str(secret_file) in str(raised.value)


def test_service_refreshes_expired_credentials():
    gmail = Gmail.__new__(Gmail)
    gmail.creds = build_credentials(expired=True)
    gmail._service = MagicMock()
    request = MagicMock()

    with patch('simplegmail.gmail.Request', return_value=request):
        service = gmail.service

    assert service is gmail._service
    gmail.creds.refresh.assert_called_once_with(request)


def test_html_payload_handles_deeply_nested_content():
    nested = '<div>' * 1000 + 'message' + '</div>' * 1000
    payload = {
        'mimeType': 'text/html',
        'body': {
            'data': base64.urlsafe_b64encode(
                f'<html><body>{nested}</body></html>'.encode()
            ).decode()
        },
    }

    parts = Gmail.__new__(Gmail)._evaluate_message_payload(
        payload, 'me', 'message-id'
    )

    assert parts == [{'part_type': 'html', 'body': f'<body>{nested}</body>'}]


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
