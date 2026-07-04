"""
File: test_get_messages.py
--------------------------
Tests for the lazy iterator behavior of Gmail.get_messages(). Uses stubbed
service objects; no HTTP requests are made.

"""

from collections.abc import Iterator

import httplib2
import pytest
from googleapiclient.errors import HttpError

import simplegmail.gmail
from simplegmail.gmail import Gmail
from simplegmail.label import Label


class FakeRequest(object):
    def __init__(self, response):
        self._response = response

    def execute(self):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeService(object):
    """Stands in for the Gmail API service object; records list() calls."""

    def __init__(self, pages):
        self.pages = pages  # responses (or exceptions) returned in order
        self.list_calls = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest(self.pages[len(self.list_calls) - 1])


class FakeCreds(object):
    def __init__(self):
        self.access_token_expired = False
        self.refresh_calls = 0

    def refresh(self, http):
        self.refresh_calls += 1
        self.access_token_expired = False


class FakeWorkerService(object):
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def http_error(status='403'):
    return HttpError(httplib2.Response({'status': status}), b'error')


def make_gmail(pages, stub_refs=True):
    gmail = Gmail.__new__(Gmail)  # skip auth in __init__
    gmail.creds = FakeCreds()
    gmail._service = FakeService(pages)
    gmail.refs_calls = []

    if stub_refs:
        # Bypass the parallel download machinery: pass message refs through
        # as-is, recording the (user_id, attachments) pair for each page.
        def fake_get_messages_from_refs(user_id, message_refs,
                                        attachments='reference'):
            gmail.refs_calls.append((user_id, attachments))
            return message_refs

        gmail._get_messages_from_refs = fake_get_messages_from_refs

    return gmail


def stub_worker_gmail(monkeypatch, builder):
    """
    Replaces the per-thread Gmail construction inside the real
    _get_messages_from_refs with a lightweight fake whose
    _build_message_from_ref calls `builder(ref)`.
    """

    workers = []

    class FakeWorkerGmail(object):
        def __init__(self, _creds=None):
            self.service = FakeWorkerService()
            workers.append(self)

        def _build_message_from_ref(self, user_id, ref, attachments):
            return builder(ref)

    monkeypatch.setattr(simplegmail.gmail, 'Gmail', FakeWorkerGmail)
    return workers


class TestGetMessages(object):

    def test_returns_lazy_iterator(self):
        gmail = make_gmail([{'messages': [{'id': '1'}]}])
        result = gmail.get_messages()
        assert isinstance(result, Iterator)
        assert not isinstance(result, list)

    def test_single_page(self):
        gmail = make_gmail([{'messages': [{'id': '1'}, {'id': '2'}]}])
        assert list(gmail.get_messages()) == [{'id': '1'}, {'id': '2'}]
        assert len(gmail._service.list_calls) == 1

    def test_pages_are_fetched_lazily(self):
        pages = [
            {'messages': [{'id': '1'}, {'id': '2'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '3'}]},
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages(page_size=2)

        # Only the first page is fetched at call time.
        assert len(gmail._service.list_calls) == 1

        assert next(it) == {'id': '1'}
        assert next(it) == {'id': '2'}
        assert len(gmail._service.list_calls) == 1  # page 2 not fetched yet

        assert next(it) == {'id': '3'}
        assert len(gmail._service.list_calls) == 2
        assert gmail._service.list_calls[1]['pageToken'] == 'tok'
        assert gmail._service.list_calls[1]['maxResults'] == 2

        with pytest.raises(StopIteration):
            next(it)

    def test_page_size_passed_as_max_results(self):
        gmail = make_gmail([{}])
        list(gmail.get_messages(page_size=42))
        call = gmail._service.list_calls[0]
        assert call['maxResults'] == 42
        assert 'pageToken' not in call

    def test_empty_mailbox(self):
        gmail = make_gmail([{}])
        assert list(gmail.get_messages()) == []

    def test_final_page_with_token_but_no_messages(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            {},
        ]
        gmail = make_gmail(pages)
        assert list(gmail.get_messages()) == [{'id': '1'}]
        assert len(gmail._service.list_calls) == 2

    def test_empty_intermediate_page_is_skipped(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 't1'},
            {'nextPageToken': 't2'},  # empty middle page, still has a token
            {'messages': [{'id': '2'}]},
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages()

        assert next(it) == {'id': '1'}
        assert next(it) == {'id': '2'}  # one next() drives two list() calls
        assert [c.get('pageToken') for c in gmail._service.list_calls] == \
            [None, 't1', 't2']
        with pytest.raises(StopIteration):
            next(it)

    def test_empty_string_next_page_token_terminates(self):
        # Termination is a truthiness check, not a key-presence check.
        gmail = make_gmail([{'messages': [{'id': '1'}], 'nextPageToken': ''}])
        assert list(gmail.get_messages()) == [{'id': '1'}]
        assert len(gmail._service.list_calls) == 1


class TestValidation(object):

    def test_invalid_attachments_raises_before_any_request(self):
        gmail = make_gmail([])
        with pytest.raises(ValueError):
            gmail.get_messages(attachments='referance')
        assert gmail._service.list_calls == []

    def test_all_valid_attachments_options_accepted(self):
        for attachments in ('ignore', 'reference', 'download'):
            gmail = make_gmail([{}])
            list(gmail.get_messages(attachments=attachments))
            assert len(gmail._service.list_calls) == 1

    def test_invalid_page_size_raises_before_any_request(self):
        gmail = make_gmail([])
        for page_size in (0, -1, 501):
            with pytest.raises(ValueError):
                gmail.get_messages(page_size=page_size)
        assert gmail._service.list_calls == []

    def test_page_size_boundaries_accepted(self):
        for page_size in (1, 500):
            gmail = make_gmail([{}])
            list(gmail.get_messages(page_size=page_size))
            assert gmail._service.list_calls[0]['maxResults'] == page_size


class TestErrorTiming(object):

    def test_first_page_error_raises_at_call_time(self):
        gmail = make_gmail([http_error()])
        with pytest.raises(HttpError):
            gmail.get_messages()

    def test_later_page_error_raises_during_iteration(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            http_error(),
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages()

        assert next(it) == {'id': '1'}
        with pytest.raises(HttpError):
            next(it)

    def test_download_error_raises_during_iteration(self):
        gmail = make_gmail([{'messages': [{'id': '1'}]}])

        def failing_get_messages_from_refs(user_id, message_refs,
                                           attachments='reference'):
            raise http_error()

        gmail._get_messages_from_refs = failing_get_messages_from_refs

        it = gmail.get_messages()  # listing succeeds; no error at call time
        with pytest.raises(HttpError):
            next(it)

    def test_error_permanently_exhausts_iterator(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            http_error(),
            {'messages': [{'id': '2'}]},  # must never be fetched
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages()

        assert next(it) == {'id': '1'}
        with pytest.raises(HttpError):
            next(it)

        # A failed iterator cannot be resumed; it is exhausted, not retried.
        with pytest.raises(StopIteration):
            next(it)
        assert len(gmail._service.list_calls) == 2


class TestIteratorContract(object):

    def test_iterator_is_single_pass(self):
        gmail = make_gmail([{'messages': [{'id': '1'}]}])
        it = gmail.get_messages()
        assert list(it) == [{'id': '1'}]
        assert list(it) == []  # second pass yields nothing

    def test_result_is_always_truthy_even_when_empty(self):
        # Documents the migration footgun: `if not messages:` is dead code.
        gmail = make_gmail([{}])
        messages = gmail.get_messages()
        assert bool(messages)
        assert list(messages) == []

    def test_result_does_not_support_indexing_or_len(self):
        gmail = make_gmail([{'messages': [{'id': '1'}]}])
        messages = gmail.get_messages()
        with pytest.raises(TypeError):
            messages[0]
        with pytest.raises(TypeError):
            len(messages)

    def test_next_with_default_on_no_match(self):
        gmail = make_gmail([{}])
        assert next(gmail.get_messages(query='no match'), None) is None
        assert len(gmail._service.list_calls) == 1

    def test_abandoning_iterator_stops_fetching(self):
        pages = [
            {'messages': [{'id': '1'}, {'id': '2'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '3'}]},
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages()
        next(it)
        it.close()  # explicit abandonment (same as `break` + GC)

        assert len(gmail._service.list_calls) == 1  # page 2 never fetched
        with pytest.raises(StopIteration):
            next(it)

    def test_two_iterators_from_same_gmail_are_independent(self):
        pages = [
            {'messages': [{'id': 'a1'}], 'nextPageToken': 'ta'},
            {'messages': [{'id': 'b1'}], 'nextPageToken': 'tb'},
            {'messages': [{'id': 'a2'}]},
            {'messages': [{'id': 'b2'}]},
        ]
        gmail = make_gmail(pages)
        it1 = gmail.get_messages()  # eagerly fetches pages[0]
        it2 = gmail.get_messages()  # eagerly fetches pages[1]

        assert next(it1) == {'id': 'a1'}
        assert next(it2) == {'id': 'b1'}
        assert next(it1) == {'id': 'a2'}  # follows 'ta', not it2's token
        assert next(it2) == {'id': 'b2'}  # follows 'tb'

        calls = gmail._service.list_calls
        assert calls[2]['pageToken'] == 'ta'
        assert calls[3]['pageToken'] == 'tb'


class TestRequestParameters(object):

    def test_all_parameters_repeated_on_every_page(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 't1'},
            {'messages': [{'id': '2'}], 'nextPageToken': 't2'},
            {'messages': [{'id': '3'}]},
        ]
        gmail = make_gmail(pages)
        list(gmail.get_messages(user_id='someone@else.com', query='is:unread',
                                include_spam_trash=True, page_size=50))

        calls = gmail._service.list_calls
        assert len(calls) == 3
        assert [c.get('pageToken') for c in calls] == [None, 't1', 't2']
        for call in calls:
            assert call['userId'] == 'someone@else.com'
            assert call['q'] == 'is:unread'
            assert call['includeSpamTrash'] is True
            assert call['maxResults'] == 50

    def test_attachments_option_forwarded_every_page(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '2'}]},
        ]
        gmail = make_gmail(pages)
        list(gmail.get_messages(attachments='download'))
        assert gmail.refs_calls == [('me', 'download'), ('me', 'download')]

    def test_label_objects_and_strings_normalized(self):
        gmail = make_gmail([{}])
        list(gmail.get_messages(labels=[Label('Custom', 'Label_7'),
                                        'Label_raw']))
        assert gmail._service.list_calls[0]['labelIds'] == ['Label_7',
                                                            'Label_raw']

    def test_user_id_forwarded_to_hydration_every_page(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '2'}]},
        ]
        gmail = make_gmail(pages)
        list(gmail.get_messages(user_id='someone@else.com'))
        assert gmail.refs_calls == [('someone@else.com', 'reference')] * 2

    def test_token_refreshed_between_pages(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '2'}]},
        ]
        gmail = make_gmail(pages)
        it = gmail.get_messages()
        assert next(it) == {'id': '1'}

        # Token expires while the consumer is paused between pages; the
        # generator must re-enter the `service` property, which refreshes.
        gmail.creds.access_token_expired = True
        assert next(it) == {'id': '2'}
        assert gmail.creds.refresh_calls == 1


class TestWrappers(object):

    @pytest.mark.parametrize('method,label_id', [
        ('get_starred_messages', 'STARRED'),
        ('get_important_messages', 'IMPORTANT'),
        ('get_unread_messages', 'UNREAD'),
        ('get_drafts', 'DRAFT'),
        ('get_sent_messages', 'SENT'),
    ])
    def test_wrapper_adds_label_and_forwards_page_size(self, method,
                                                       label_id):
        gmail = make_gmail([{}])
        result = getattr(gmail, method)(page_size=9)
        assert isinstance(result, Iterator)
        assert list(result) == []

        call = gmail._service.list_calls[0]
        assert call['labelIds'] == [label_id]
        assert call['maxResults'] == 9
        assert call['includeSpamTrash'] is False

    @pytest.mark.parametrize('method,label_id', [
        ('get_trash_messages', 'TRASH'),
        ('get_spam_messages', 'SPAM'),
    ])
    def test_spam_trash_wrappers_forward_correctly(self, method, label_id):
        gmail = make_gmail([{}])
        list(getattr(gmail, method)(page_size=9))

        call = gmail._service.list_calls[0]
        assert call['labelIds'] == [label_id]
        # The positional True must land in include_spam_trash, not page_size.
        assert call['includeSpamTrash'] is True
        assert call['maxResults'] == 9

    def test_get_unread_inbox_forwards_arguments(self):
        gmail = make_gmail([{'messages': [{'id': '1'}]}])
        result = gmail.get_unread_inbox(attachments='ignore', page_size=7)

        assert isinstance(result, Iterator)
        assert list(result) == [{'id': '1'}]

        call = gmail._service.list_calls[0]
        assert call['labelIds'] == ['INBOX', 'UNREAD']
        assert call['maxResults'] == 7
        assert gmail.refs_calls == [('me', 'ignore')]

    @pytest.mark.parametrize('method', [
        'get_starred_messages', 'get_important_messages',
        'get_unread_messages', 'get_drafts', 'get_sent_messages',
    ])
    def test_wrapper_forwards_user_id_query_and_spam_trash(self, method):
        gmail = make_gmail([{}])
        list(getattr(gmail, method)(user_id='someone@else.com',
                                    query='has:attachment',
                                    include_spam_trash=True))
        call = gmail._service.list_calls[0]
        assert call['userId'] == 'someone@else.com'
        assert call['q'] == 'has:attachment'
        assert call['includeSpamTrash'] is True

    def test_get_unread_inbox_forwards_user_id_and_query(self):
        gmail = make_gmail([{}])
        list(gmail.get_unread_inbox(user_id='someone@else.com',
                                    query='has:attachment'))
        call = gmail._service.list_calls[0]
        assert call['userId'] == 'someone@else.com'
        assert call['q'] == 'has:attachment'

    def test_wrapper_combines_user_labels_with_its_own(self):
        gmail = make_gmail([{}])
        list(gmail.get_starred_messages(labels=['MyLabel']))
        assert gmail._service.list_calls[0]['labelIds'] == ['MyLabel',
                                                            'STARRED']

    def test_wrappers_are_lazy(self):
        pages = [
            {'messages': [{'id': '1'}], 'nextPageToken': 'tok'},
            {'messages': [{'id': '2'}]},
        ]
        gmail = make_gmail(pages)
        gmail.get_starred_messages()
        assert len(gmail._service.list_calls) == 1  # first page only

    def test_wrapper_validation_is_eager(self):
        gmail = make_gmail([])
        with pytest.raises(ValueError):
            gmail.get_starred_messages(attachments='bogus')
        assert gmail._service.list_calls == []


class TestGetMessagesFromRefs(object):
    """Tests the real threaded download machinery, with only the per-thread
    Gmail construction stubbed out."""

    def test_order_preserved_across_threads(self, monkeypatch):
        refs = [{'id': str(i)} for i in range(25)]
        workers = stub_worker_gmail(monkeypatch, lambda ref: ref)
        gmail = make_gmail([], stub_refs=False)

        result = gmail._get_messages_from_refs('me', refs)

        assert result == refs
        assert len(workers) == 3  # ceil(25 refs / 10 per thread)
        assert all(w.service.closed for w in workers)

    def test_worker_http_error_propagates(self, monkeypatch):
        # Without the error capture, a worker exception kills its thread and
        # the caller crashes with TypeError from sum() over a None slot.
        refs = [{'id': str(i)} for i in range(25)]

        def builder(ref):
            if ref['id'] == '7':
                raise http_error()
            return ref

        stub_worker_gmail(monkeypatch, builder)
        gmail = make_gmail([], stub_refs=False)

        with pytest.raises(HttpError):
            gmail._get_messages_from_refs('me', refs)

    def test_error_in_last_thread_propagates(self, monkeypatch):
        refs = [{'id': str(i)} for i in range(25)]

        def builder(ref):
            if ref['id'] == '24':  # last ref, handled by the last thread
                raise http_error()
            return ref

        stub_worker_gmail(monkeypatch, builder)
        gmail = make_gmail([], stub_refs=False)

        with pytest.raises(HttpError):
            gmail._get_messages_from_refs('me', refs)

    def test_worker_failure_does_not_abort_other_threads(self, monkeypatch):
        refs = [{'id': str(i)} for i in range(25)]
        attempted = []  # list.append is thread-safe under the GIL

        def builder(ref):
            attempted.append(ref['id'])
            if ref['id'] == '7':  # fails in the first thread's batch (0-8)
                raise http_error()
            return ref

        workers = stub_worker_gmail(monkeypatch, builder)
        gmail = make_gmail([], stub_refs=False)

        with pytest.raises(HttpError):
            gmail._get_messages_from_refs('me', refs)

        # All threads are joined before the error is raised: the other two
        # batches (refs 9-24) run to completion and close their services.
        assert set(str(i) for i in range(9, 25)) <= set(attempted)
        assert len(workers) == 3
        assert sum(w.service.closed for w in workers) == 2

    def test_base_exception_in_worker_propagates(self, monkeypatch):
        class FakeInterrupt(BaseException):
            pass

        def builder(ref):
            raise FakeInterrupt()

        stub_worker_gmail(monkeypatch, builder)
        gmail = make_gmail([], stub_refs=False)

        with pytest.raises(FakeInterrupt):
            gmail._get_messages_from_refs('me', [{'id': '0'}])

    def test_empty_refs_spawn_no_threads(self, monkeypatch):
        workers = stub_worker_gmail(monkeypatch, lambda ref: ref)
        gmail = make_gmail([], stub_refs=False)

        assert gmail._get_messages_from_refs('me', []) == []
        assert workers == []

    def test_sequential_path(self, monkeypatch):
        refs = [{'id': '0'}, {'id': '1'}]
        workers = stub_worker_gmail(monkeypatch, lambda ref: ref)
        gmail = make_gmail([], stub_refs=False)
        gmail._build_message_from_ref = (
            lambda user_id, ref, attachments: ref
        )

        result = gmail._get_messages_from_refs('me', refs, parallel=False)

        assert result == refs
        assert workers == []  # no per-thread Gmail instances

    def test_end_to_end_pagination_with_real_thread_machinery(self,
                                                              monkeypatch):
        pages = [
            {'messages': [{'id': str(i)} for i in range(15)],
             'nextPageToken': 'tok'},
            {'messages': [{'id': '15'}]},
        ]
        stub_worker_gmail(monkeypatch, lambda ref: ref)
        gmail = make_gmail(pages, stub_refs=False)

        result = list(gmail.get_messages(page_size=15))

        assert result == pages[0]['messages'] + pages[1]['messages']
        assert len(gmail._service.list_calls) == 2
