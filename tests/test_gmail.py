import base64
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
import json
from unittest.mock import MagicMock, call, patch

import pytest
from googleapiclient.errors import HttpError

from simplegmail import label
from simplegmail.gmail import Gmail
from simplegmail.message import Message


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


def parse_message_resource(message_resource):
    return BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(message_resource['raw'])
    )


def build_reply_to(headers, subject='Original subject', thread_id='thread-id'):
    return Message(
        service=MagicMock(),
        creds=MagicMock(),
        user_id='me',
        msg_id='message-id',
        thread_id=thread_id,
        recipient='recipient@example.com',
        sender='sender@example.com',
        subject=subject,
        date='date',
        snippet='snippet',
        headers=headers,
    )


def test_uses_injected_credentials_without_loading_token_file():
    creds = build_credentials()
    service = MagicMock()

    with patch.object(Gmail, '_get_credentials') as load:
        with patch('simplegmail.gmail.build', return_value=service) as build:
            gmail = Gmail(credentials=creds)

    assert gmail.creds is creds
    assert gmail.service is service
    load.assert_not_called()
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


def test_send_message_uses_existing_builder_and_shared_sender():
    gmail = build_gmail()
    message_resource = {'raw': 'encoded-message'}
    sent_message = object()
    gmail._create_message = MagicMock(return_value=message_resource)
    gmail._send_message = MagicMock(return_value=sent_message)

    result = gmail.send_message(
        sender='sender@example.com',
        to='recipient@example.com',
        user_id='account@example.com',
    )

    gmail._create_message.assert_called_once()
    gmail._send_message.assert_called_once_with(
        message_resource, 'account@example.com'
    )
    assert result is sent_message


@pytest.mark.parametrize(
    ('headers', 'references'),
    [
        (
            {'Message-ID': '<parent@example.com>'},
            '<parent@example.com>',
        ),
        (
            {
                'Message-ID': '<parent@example.com>',
                'In-Reply-To': '<grandparent@example.com>',
            },
            '<grandparent@example.com> <parent@example.com>',
        ),
        (
            {
                'message-id': '<parent@example.com>',
                'references': '<first@example.com> <second@example.com>',
                'in-reply-to': '<ignored@example.com>',
            },
            '<first@example.com> <second@example.com> <parent@example.com>',
        ),
        (
            {
                'Message-ID': '<parent@example.com>',
                'In-Reply-To': '<first@example.com> <second@example.com>',
            },
            '<parent@example.com>',
        ),
    ],
)
def test_send_message_builds_threaded_reply(headers, references):
    gmail = build_gmail()
    sent_message = object()
    gmail._send_message = MagicMock(return_value=sent_message)

    result = gmail.send_message(
        sender='me@example.com',
        to='sender@example.com',
        msg_plain='Reply body',
        reply_to=build_reply_to(headers),
    )

    message_resource = gmail._send_message.call_args.args[0]
    message = parse_message_resource(message_resource)
    gmail._send_message.assert_called_once_with(message_resource, 'me')
    assert message_resource['threadId'] == 'thread-id'
    assert message['Subject'] == 'Original subject'
    assert message['In-Reply-To'] == '<parent@example.com>'
    assert message['References'] == references
    assert message.get_body().get_content().strip() == 'Reply body'
    assert result is sent_message


@pytest.mark.parametrize(
    ('reply_to', 'subject', 'error'),
    [
        (
            build_reply_to(
                {'Message-ID': '<parent@example.com>'}, thread_id=''
            ),
            '',
            'reply_to must have a thread ID',
        ),
        (
            build_reply_to({}),
            '',
            'reply_to must have a Message-ID header',
        ),
        (
            build_reply_to({'Message-ID': '<parent@example.com>'}),
            'Different subject',
            'reply subject must match',
        ),
    ],
)
def test_send_message_rejects_invalid_reply(reply_to, subject, error):
    gmail = build_gmail()
    gmail._send_message = MagicMock()

    with pytest.raises(ValueError, match=error):
        gmail.send_message(
            sender='me@example.com',
            to='sender@example.com',
            subject=subject,
            reply_to=reply_to,
        )

    gmail._send_message.assert_not_called()


def test_send_email_message_encodes_and_sends_mime_message():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    message_api = gmail._service.users.return_value.messages.return_value
    message_ref = {'id': 'message-id'}
    message_api.send.return_value.execute.return_value = message_ref
    sent_message = object()
    gmail._build_message_from_ref = MagicMock(return_value=sent_message)
    message = EmailMessage()
    message['From'] = 'sender@example.com'
    message['To'] = 'recipient@example.com'
    message['Subject'] = 'Subject'
    message.set_content('Body')
    message.add_attachment(
        b'attachment',
        maintype='application',
        subtype='octet-stream',
        filename='attachment.bin',
    )
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = gmail.send_email_message(
        message, user_id='account@example.com'
    )

    message_api.send.assert_called_once_with(
        userId='account@example.com',
        body={'raw': encoded_message},
    )
    gmail._build_message_from_ref.assert_called_once_with(
        'account@example.com', message_ref, 'reference'
    )
    assert result is sent_message


def test_send_email_message_propagates_api_errors():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    response = MagicMock(status=400, reason='Bad Request')
    error = HttpError(response, b'{}')
    message_api = gmail._service.users.return_value.messages.return_value
    message_api.send.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as raised:
        gmail.send_email_message(EmailMessage())

    assert raised.value is error


def test_create_draft_uses_message_builder_and_returns_api_resource():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    gmail._create_message = MagicMock(return_value={'raw': 'encoded-message'})
    params = {
        'sender': 'sender@example.com',
        'to': 'recipient@example.com',
        'subject': 'Subject',
        'msg_html': '<p>HTML</p>',
        'msg_plain': 'Plain',
        'cc': ['cc@example.com'],
        'bcc': ['bcc@example.com'],
        'attachments': ['attachment.txt'],
        'signature': True,
        'user_id': 'account@example.com',
    }
    draft = {'id': 'draft-id', 'message': {'id': 'message-id'}}
    drafts = gmail._service.users.return_value.drafts.return_value
    drafts.create.return_value.execute.return_value = draft

    result = gmail.create_draft(**params)

    gmail._create_message.assert_called_once_with(**params)
    drafts.create.assert_called_once_with(
        userId='account@example.com',
        body={'message': {'raw': 'encoded-message'}},
    )
    assert result is draft


@pytest.mark.parametrize(
    ('msg_plain', 'msg_html', 'content_types'),
    [
        ('Plain body', None, ['text/plain']),
        (None, '<p>HTML body</p>', ['text/html']),
        (
            'Plain body',
            '<p>HTML body</p>',
            ['text/plain', 'text/html'],
        ),
    ],
)
def test_create_message_preserves_body_with_attachments(
    tmp_path, msg_plain, msg_html, content_types
):
    attachment = tmp_path / 'attachment.txt'
    attachment.write_text('Attachment')
    gmail = build_gmail()

    message = parse_message_resource(gmail._create_message(
        sender='sender@example.com',
        to='recipient@example.com',
        msg_plain=msg_plain,
        msg_html=msg_html,
        attachments=[str(attachment)],
    ))

    assert message.get_content_type() == 'multipart/mixed'
    body, saved_attachment = message.get_payload()
    assert body.get_content_type() == 'multipart/alternative'
    assert [part.get_content_type() for part in body.get_payload()] == (
        content_types
    )
    assert [part.get_content().strip() for part in body.get_payload()] == [
        content for content in (msg_plain, msg_html) if content
    ]
    assert saved_attachment.get_content_disposition() == 'attachment'
    assert saved_attachment.get_content().strip() == 'Attachment'
    assert not any(
        part.get_content_type() == 'multipart/related'
        for part in message.walk()
    )


def test_create_message_with_only_an_attachment_has_no_empty_body(tmp_path):
    attachment = tmp_path / 'attachment.txt'
    attachment.write_text('Attachment')
    gmail = build_gmail()

    message = parse_message_resource(gmail._create_message(
        sender='sender@example.com',
        to='recipient@example.com',
        attachments=[str(attachment)],
    ))

    assert message.get_content_type() == 'multipart/mixed'
    assert len(message.get_payload()) == 1
    assert message.get_payload(0).get_content_disposition() == 'attachment'


@pytest.mark.parametrize(
    ('filename', 'data'),
    [
        ('binary.bin', b'\x00\xff\x10binary'),
        ('non-utf8.txt', b'\xff\xfeplain text'),
    ],
)
def test_create_message_preserves_attachment_bytes(tmp_path, filename, data):
    attachment = tmp_path / filename
    attachment.write_bytes(data)
    gmail = build_gmail()

    message = parse_message_resource(gmail._create_message(
        sender='sender@example.com',
        to='recipient@example.com',
        attachments=[str(attachment)],
    ))

    saved_attachment = message.get_payload(0)
    assert saved_attachment.get_filename() == filename
    assert saved_attachment.get_payload(decode=True) == data


def test_create_message_without_attachments_remains_multipart_alternative():
    gmail = build_gmail()

    message_resource = gmail._create_message(
        sender='sender@example.com',
        to='recipient@example.com',
        msg_plain='Plain body',
        msg_html='<p>HTML body</p>',
    )
    message = parse_message_resource(message_resource)

    assert set(message_resource) == {'raw'}
    assert message.get_content_type() == 'multipart/alternative'
    assert [part.get_content_type() for part in message.get_payload()] == [
        'text/plain',
        'text/html',
    ]


@pytest.mark.parametrize(
    ('method_name', 'required_labels', 'include_spam_trash'),
    [
        ('get_unread_inbox', [label.INBOX, label.UNREAD], False),
        ('get_starred_messages', [label.STARRED], False),
        ('get_important_messages', [label.IMPORTANT], False),
        ('get_unread_messages', [label.UNREAD], False),
        ('get_drafts', [label.DRAFT], False),
        ('get_sent_messages', [label.SENT], False),
        ('get_trash_messages', [label.TRASH], True),
        ('get_spam_messages', [label.SPAM], True),
    ],
)
def test_filtered_getters_forward_options_without_mutating_labels(
    method_name, required_labels, include_spam_trash
):
    gmail = build_gmail()
    gmail.get_messages = MagicMock(return_value=[])
    labels = [label.PERSONAL]

    result = getattr(gmail, method_name)(
        labels=labels,
        query='query',
        attachments='ignore',
    )

    assert result == []
    assert labels == [label.PERSONAL]
    gmail.get_messages.assert_called_once_with(
        'me',
        [label.PERSONAL] + required_labels,
        'query',
        'ignore',
        include_spam_trash,
    )


@pytest.mark.parametrize('attachments', [None, '', 'references', True])
def test_get_messages_rejects_invalid_attachment_mode(attachments):
    gmail = build_gmail()
    gmail._service = MagicMock()

    with pytest.raises(ValueError, match='attachments must be'):
        gmail.get_messages(attachments=attachments)

    gmail._service.users.assert_not_called()


def test_get_messages_passes_metadata_option_to_message_retrieval():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    refs = [{'id': 'message-1'}, {'id': 'message-2'}]
    messages = gmail._service.users.return_value.messages.return_value
    messages.list.return_value.execute.side_effect = [
        {'messages': refs[:1], 'nextPageToken': 'next'},
        {'messages': refs[1:]},
    ]
    gmail._get_messages_from_refs = MagicMock(return_value=[])

    gmail.get_messages(metadata_only=True)

    assert messages.list.call_args_list == [
        call(userId='me', q='', labelIds=[], includeSpamTrash=False),
        call(
            userId='me', q='', labelIds=[], includeSpamTrash=False,
            pageToken='next',
        ),
    ]
    gmail._get_messages_from_refs.assert_called_once_with(
        'me', refs, 'reference', metadata_only=True
    )


def test_get_messages_limits_results_across_pages():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    messages = gmail._service.users.return_value.messages.return_value
    first_page = [{'id': str(i)} for i in range(500)]
    last_page = [{'id': '500'}]
    messages.list.return_value.execute.side_effect = [
        {'messages': first_page, 'nextPageToken': 'next'},
        {'messages': last_page, 'nextPageToken': 'unused'},
    ]
    gmail._get_messages_from_refs = MagicMock(return_value=[])

    gmail.get_messages(max_results=501)

    assert messages.list.call_args_list == [
        call(
            userId='me', q='', labelIds=[], includeSpamTrash=False,
            maxResults=500,
        ),
        call(
            userId='me', q='', labelIds=[], includeSpamTrash=False,
            maxResults=1, pageToken='next',
        ),
    ]
    gmail._get_messages_from_refs.assert_called_once_with(
        'me', first_page + last_page, 'reference', metadata_only=False
    )


@pytest.mark.parametrize('max_results', [0, -1, 1.5, '1', True])
def test_get_messages_rejects_invalid_max_results(max_results):
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()

    with pytest.raises(
        ValueError, match='max_results must be a positive integer'
    ):
        gmail.get_messages(max_results=max_results)

    gmail._service.users.assert_not_called()


def test_builds_metadata_message_without_parsing_body():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    messages = gmail._service.users.return_value.messages.return_value
    messages.get.return_value.execute.return_value = {
        'id': 'message-id',
        'threadId': 'thread-id',
        'sizeEstimate': 1234,
        'payload': {
            'headers': [
                {'name': 'From', 'value': 'sender@example.com'},
                {'name': 'To', 'value': 'recipient@example.com'},
                {'name': 'Subject', 'value': 'Subject'},
                {'name': 'Date', 'value': 'Date'},
            ],
        },
    }

    message = gmail._build_message_from_ref(
        'me', {'id': 'message-id'}, metadata_only=True
    )

    messages.get.assert_called_once_with(
        userId='me', id='message-id', format='metadata'
    )
    assert message.sender == 'sender@example.com'
    assert message.recipient == 'recipient@example.com'
    assert message.subject == 'Subject'
    assert message.date == 'Date'
    assert message.size_estimate == 1234
    assert message.plain is None
    assert message.html is None
    assert message.attachments == []


def test_full_message_retrieval_remains_the_default():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    messages = gmail._service.users.return_value.messages.return_value
    messages.get.return_value.execute.return_value = {
        'id': 'message-id',
        'threadId': 'thread-id',
        'labelIds': ['INBOX'],
        'snippet': 'Snippet',
        'payload': {
            'headers': [],
            'mimeType': 'text/plain',
            'body': {
                'data': base64.urlsafe_b64encode(b'Body').decode(),
            },
        },
    }
    message = gmail._build_message_from_ref('me', {'id': 'message-id'})

    messages.get.assert_called_once_with(userId='me', id='message-id')
    assert message.plain == 'Body'
    assert message.label_ids == ['INBOX']


def test_parses_quoted_cc_and_bcc_addresses():
    gmail = build_gmail()
    gmail.creds.expired = False
    gmail._service = MagicMock()
    gmail._service.users.return_value.messages.return_value.get.return_value \
        .execute.return_value = {
            'id': 'message-id',
            'threadId': 'thread-id',
            'payload': {
                'headers': [
                    {
                        'name': 'Cc',
                        'value': '"Doe, John" <john@example.com>, jane@example.com',
                    },
                    {
                        'name': 'Bcc',
                        'value': 'first@example.com,second@example.com',
                    },
                ],
                'mimeType': 'text/plain',
                'body': {'data': ''},
            },
        }

    message = gmail._build_message_from_ref('me', {'id': 'message-id'})

    assert message.cc == [
        '"Doe, John" <john@example.com>',
        'jane@example.com',
    ]
    assert message.bcc == ['first@example.com', 'second@example.com']


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


def test_external_text_payload_is_downloaded_as_message_body():
    gmail = build_gmail()
    gmail._service = MagicMock()
    attachments = gmail._service.users.return_value.messages.return_value \
        .attachments.return_value
    attachments.get.return_value.execute.return_value = {
        'data': base64.urlsafe_b64encode('ol\xe1'.encode('iso-8859-1')).decode(),
    }
    payload = {
        'mimeType': 'text/plain',
        'filename': '',
        'headers': [
            {'name': 'Content-Type', 'value': 'text/plain; charset=iso-8859-1'},
        ],
        'body': {'attachmentId': 'body-id'},
    }

    parts = gmail._evaluate_message_payload(payload, 'me', 'message-id')

    assert parts == [{'part_type': 'plain', 'body': 'ol\xe1'}]
    attachments.get.assert_called_once_with(
        userId='me', messageId='message-id', id='body-id'
    )


def test_message_body_decodes_unpadded_base64url():
    payload = {
        'mimeType': 'text/plain',
        'body': {'data': '_w'},
    }

    parts = Gmail.__new__(Gmail)._evaluate_message_payload(
        payload, 'me', 'message-id'
    )

    assert parts == [{'part_type': 'plain', 'body': '\ufffd'}]


def test_inline_attachment_data_is_available_without_an_attachment_id():
    payload = {
        'mimeType': 'application/octet-stream',
        'filename': 'data.bin',
        'headers': [],
        'body': {'data': '_w'},
    }

    parts = Gmail.__new__(Gmail)._evaluate_message_payload(
        payload, 'me', 'message-id'
    )

    assert parts == [{
        'part_type': 'attachment',
        'filetype': 'application/octet-stream',
        'filename': 'data.bin',
        'attachment_id': None,
        'data': b'\xff',
    }]


def test_inline_image_is_retained_as_an_attachment():
    gmail = build_gmail()
    gmail._service = MagicMock()
    payload = {
        'mimeType': 'image/png',
        'filename': '',
        'headers': [
            {'name': 'Content-Disposition', 'value': 'inline'},
        ],
        'body': {'attachmentId': 'image-id'},
    }

    parts = gmail._evaluate_message_payload(payload, 'me', 'message-id')

    assert parts == [{
        'part_type': 'attachment',
        'filetype': 'image/png',
        'filename': 'unknown',
        'attachment_id': 'image-id',
        'data': None,
    }]


def test_parallel_retrieval_preserves_order_and_closes_services():
    gmail = build_gmail()
    message_refs = [{'id': str(i)} for i in range(21)]
    workers = []

    def build_message(
        user_id,
        message_ref,
        attachments,
        metadata_only=False,
    ):
        assert metadata_only is True
        return message_ref['id']

    with patch(
        'simplegmail.gmail.Gmail',
        side_effect=lambda **_: build_worker(workers, build_message),
    ) as gmail_class:
        messages = Gmail._get_messages_from_refs(
            gmail,
            'me',
            message_refs,
            attachments='ignore',
            metadata_only=True,
        )

    assert messages == [ref['id'] for ref in message_refs]
    assert gmail_class.call_args_list == [call(credentials=gmail.creds)] * 3
    assert all(worker.service.close.call_count == 1 for worker in workers)


def test_small_retrieval_reuses_current_service():
    gmail = build_gmail()
    gmail._build_message_from_ref = MagicMock(
        side_effect=lambda _user_id, ref, _attachments, **_: ref['id']
    )
    message_refs = [{'id': str(i)} for i in range(10)]

    with patch('simplegmail.gmail.Gmail') as gmail_class:
        messages = Gmail._get_messages_from_refs(gmail, 'me', message_refs)

    assert messages == [ref['id'] for ref in message_refs]
    assert gmail._build_message_from_ref.call_count == 10
    gmail_class.assert_not_called()


def test_parallel_retrieval_propagates_worker_errors_and_closes_services():
    gmail = build_gmail()
    message_refs = [{'id': str(i)} for i in range(11)]
    workers = []
    error = RuntimeError('download failed')

    def build_message(
        user_id,
        message_ref,
        attachments,
        metadata_only=False,
    ):
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
