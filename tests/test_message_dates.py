"""
File: test_message_dates.py
---------------------------
Tests for the two date fields on Message: `headerDate` (parsed from the
RFC 2822 Date header) and `internalDate` (Gmail's internal received
timestamp, in epoch milliseconds). Uses stubbed service objects; no HTTP
requests are made.

"""

import dateutil.parser as parser

from simplegmail.gmail import Gmail


class FakeRequest(object):
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class FakeService(object):
    """Stands in for the Gmail API service; serves a single message JSON."""

    def __init__(self, message_json):
        self._message_json = message_json

    def users(self):
        return self

    def messages(self):
        return self

    def get(self, userId, id):
        return FakeRequest(self._message_json)


class FakeCreds(object):
    access_token_expired = False


DATE_HEADER = 'Tue, 01 Jul 2025 12:30:00 +0000'
INTERNAL_DATE_MS = 1751370600123  # arbitrary epoch-ms value


def message_json(**overrides):
    base = {
        'id': 'msg1',
        'threadId': 'thread1',
        'snippet': 'hello there',
        'internalDate': str(INTERNAL_DATE_MS),  # the API returns a string
        'payload': {
            'mimeType': 'multipart/mixed',
            'body': {},
            'headers': [
                {'name': 'From', 'value': 'sender@example.com'},
                {'name': 'To', 'value': 'recipient@example.com'},
                {'name': 'Subject', 'value': 'Hi'},
                {'name': 'Date', 'value': DATE_HEADER},
            ],
        },
    }
    base.update(overrides)
    return base


def build_message(msg_json):
    gmail = Gmail.__new__(Gmail)  # skip auth in __init__
    gmail.creds = FakeCreds()
    gmail._service = FakeService(msg_json)
    return gmail._build_message_from_ref('me', {'id': 'msg1'})


def payload_without_date_header():
    payload = message_json()['payload']
    payload['headers'] = [
        h for h in payload['headers'] if h['name'] != 'Date'
    ]
    return payload


class TestHeaderDate(object):

    def test_parsed_from_date_header(self):
        msg = build_message(message_json())
        expected = str(parser.parse(DATE_HEADER).astimezone())
        assert msg.headerDate == expected

    def test_unparseable_header_kept_verbatim(self):
        json = message_json()
        json['payload']['headers'] = [
            {'name': 'Date', 'value': 'not a real date'},
        ]
        msg = build_message(json)
        assert msg.headerDate == 'not a real date'

    def test_missing_date_header_is_empty_string(self):
        msg = build_message(message_json(payload=payload_without_date_header()))
        assert msg.headerDate == ''

    def test_old_date_attribute_is_gone(self):
        # `date` was renamed to `headerDate`; it must not linger as an alias
        # that could silently diverge.
        msg = build_message(message_json())
        assert not hasattr(msg, 'date')


class TestInternalDate(object):

    def test_exposed_as_epoch_milliseconds_int(self):
        msg = build_message(message_json())
        assert msg.internalDate == INTERNAL_DATE_MS
        assert isinstance(msg.internalDate, int)

    def test_missing_internal_date_is_none(self):
        json = message_json()
        del json['internalDate']
        msg = build_message(json)
        assert msg.internalDate is None

    def test_independent_of_date_header(self):
        # internalDate comes from Gmail's own metadata, not from headers.
        msg = build_message(message_json(payload=payload_without_date_header()))
        assert msg.internalDate == INTERNAL_DATE_MS
