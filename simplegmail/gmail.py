"""
File: gmail.py
--------------
Home to the main Gmail service object. Currently supports sending mail (with
attachments) and retrieving mail with the full suite of Gmail search options.

"""

import base64
import html
import math
import mimetypes
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from email import encoders
from email.message import EmailMessage
from email.message import Message as MIMEMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses, parseaddr

from bs4 import BeautifulSoup
from dateutil import parser
from google.auth.credentials import Credentials as GoogleCredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from simplegmail import label
from simplegmail.attachment import Attachment, _decode_base64url
from simplegmail.label import Label
from simplegmail.message import Message

_LabelOrId = Label | str


class Gmail:
    """
    The Gmail class which serves as the entrypoint for the Gmail service API.

    Args:
        client_secret_file: The path of the user's client secret file.
        creds_file: The path of the auth credentials file (created on first
            call).
        access_type: Whether to request a refresh token for usage without a
            user necessarily present. Either 'online' or 'offline'.
        noauth_local_webserver: Whether to suppress opening the authorization
            URL in a browser. The local callback server is always required.
        credentials: Existing google-auth credentials. When provided, file-based
            authentication is skipped.

    Attributes:
        client_secret_file (str): The name of the user's client secret file.
        service (googleapiclient.discovery.Resource): The Gmail service object.

    """

    # Allow Gmail to read and write emails, and access settings like aliases.
    _SCOPES = (
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.settings.basic'
    )
    # Gmail's users.messages.list API allows at most 500 results per page.
    _MAX_MESSAGES_PER_PAGE = 500

    # If you don't have a client secret file, follow the instructions at:
    # https://developers.google.com/gmail/api/quickstart/python
    # Make sure the client secret file is in the root directory of your app.

    def __init__(
        self,
        client_secret_file: str = 'client_secret.json',
        creds_file: str = 'gmail_token.json',
        access_type: str = 'offline',
        noauth_local_webserver: bool = False,
        credentials: GoogleCredentials | None = None,
    ) -> None:
        self.client_secret_file = client_secret_file
        self.creds_file = creds_file

        if credentials is None:
            self.creds = self._get_credentials(
                access_type, noauth_local_webserver
            )
        else:
            self.creds = credentials

        self._service = build(
            'gmail', 'v1', credentials=self.creds, cache_discovery=False
        )

    def _get_credentials(
        self,
        access_type: str,
        noauth_local_webserver: bool,
    ) -> Credentials:
        creds = None
        if os.path.exists(self.creds_file):
            with suppress(ValueError):
                creds = Credentials.from_authorized_user_file(
                    self.creds_file, self._SCOPES
                )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secret_file, self._SCOPES
                    )
                except FileNotFoundError as error:
                    raise FileNotFoundError(
                        f"Your client secret file '{self.client_secret_file}' "
                        "is nonexistent. Follow the setup instructions at "
                        "https://developers.google.com/gmail/api/quickstart/"
                        "python."
                    ) from error

                creds = self._run_auth_flow(
                    flow, access_type, noauth_local_webserver
                )

            with open(self.creds_file, 'w') as token:
                token.write(creds.to_json())

        return creds

    @staticmethod
    def _run_auth_flow(
        flow: InstalledAppFlow,
        access_type: str,
        noauth_local_webserver: bool,
    ) -> Credentials:
        for port in (8080, 8090, 0):
            try:
                return flow.run_local_server(
                    port=port,
                    open_browser=not noauth_local_webserver,
                    access_type=access_type,
                    prompt='consent',
                )
            except OSError:
                if port == 0:
                    raise

    @property
    def service(self) -> Resource:
        # Since the token is only used through calls to the service object,
        # this ensure that the token is always refreshed before use.
        if self.creds.expired:
            self.creds.refresh(Request())

        return self._service

    def send_message(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: str | None = None,
        msg_plain: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
        signature: bool = False,
        user_id: str = 'me',
        reply_to: Message | None = None,
    ) -> Message:
        """
        Sends an email.

        Args:
            sender: The email address the message is being sent from.
            to: The email address the message is being sent to.
            subject: The subject line of the email.
            msg_html: The HTML message of the email.
            msg_plain: The plain text alternate message of the email. This is
                often displayed on slow or old browsers, or if the HTML message
                is not provided.
            cc: The list of email addresses to be cc'd.
            bcc: The list of email addresses to be bcc'd.
            attachments: The list of attachment file names.
            signature: Whether the account signature should be added to the
                message.
            user_id: The address of the sending account. 'me' for the
                default address associated with the account.
            reply_to: The message being replied to. When provided, the new
                message is sent in the same Gmail thread.

        Returns:
            The Message object representing the sent message.

        Raises:
            ValueError: The reply lacks the metadata required for threading,
                or its subject does not match the original message.
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        msg = self._create_message(
            sender, to, subject, msg_html, msg_plain, cc=cc, bcc=bcc,
            attachments=attachments, signature=signature, user_id=user_id,
            reply_to=reply_to,
        )
        return self._send_message(msg, user_id)

    def send_email_message(
        self,
        message: EmailMessage,
        user_id: str = 'me'
    ) -> Message:
        """Sends a standard library EmailMessage.

        Args:
            message: The fully constructed email message to send.
            user_id: The address of the sending account. 'me' for the default
                address associated with the account.

        Returns:
            The Message object representing the sent message.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return self._send_message({'raw': raw}, user_id)

    def create_draft(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: str | None = None,
        msg_plain: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
        signature: bool = False,
        user_id: str = 'me'
    ) -> dict:
        """Creates an email draft.

        Args:
            sender: The email address the message is being sent from.
            to: The email address the message is being sent to.
            subject: The subject line of the email.
            msg_html: The HTML message of the email.
            msg_plain: The plain text alternate message of the email.
            cc: The list of email addresses to be cc'd.
            bcc: The list of email addresses to be bcc'd.
            attachments: The list of attachment file names.
            signature: Whether the account signature should be added to the
                message.
            user_id: The address of the account creating the draft. 'me' for
                the default address associated with the account.

        Returns:
            The draft resource returned by the Gmail API.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        message = self._create_message(
            sender=sender,
            to=to,
            subject=subject,
            msg_html=msg_html,
            msg_plain=msg_plain,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            signature=signature,
            user_id=user_id
        )
        return self.service.users().drafts().create(
            userId=user_id,
            body={'message': message}
        ).execute()

    def get_unread_inbox(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> list[Message]:
        """
        Gets unread messages from your inbox.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Labels that messages must match.
            query: A Gmail query to match.
            attachments: Accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.INBOX]
        return self.get_unread_messages(
            user_id, labels, query, attachments
        )

    def get_starred_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> list[Message]:
        """
        Gets starred messages from your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: Whether to include messages from spam or trash.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.STARRED]
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_important_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> list[Message]:
        """
        Gets messages marked important from your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: Whether to include messages from spam or trash.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.IMPORTANT]
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_unread_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> list[Message]:
        """
        Gets unread messages from your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: Whether to include messages from spam or trash.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.UNREAD]
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_drafts(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> list[Message]:
        """
        Gets drafts saved in your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: Whether to include messages from spam or trash.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.DRAFT]
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_sent_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> list[Message]:
        """
        Gets sent messages from your account.

         Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: Whether to include messages from spam or trash.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.SENT]
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_trash_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> list[Message]:

        """
        Gets messages in your trash from your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        labels = list(labels or []) + [label.TRASH]
        return self.get_messages(user_id, labels, query, attachments, True)

    def get_spam_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> list[Message]:
        """
        Gets messages marked as spam from your account.

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
            labels: Label IDs messages must match.
            query: A Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """


        labels = list(labels or []) + [label.SPAM]
        return self.get_messages(user_id, labels, query, attachments, True)

    def get_messages(
        self,
        user_id: str = 'me',
        labels: list[_LabelOrId] | None = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False,
        metadata_only: bool = False,
        max_results: int | None = None
    ) -> list[Message]:
        """
        Gets messages from your account.

        Args:
            user_id: the user's email address. Default 'me', the authenticated
                user.
            labels: label IDs messages must match.
            query: a Gmail query to match.
            attachments: accepted values are 'ignore' which completely
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash: whether to include messages from spam or trash.
            metadata_only: whether to retrieve headers without message bodies
                or attachments. Default False.
            max_results: the maximum total number of messages to retrieve.
                Default None, which retrieves every matching message.

        Returns:
            A list of message objects.

        Raises:
            ValueError: `attachments` is invalid or `max_results` is not a
                positive integer.
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if labels is None:
            labels = []
        if attachments not in ('ignore', 'reference', 'download'):
            raise ValueError(
                "attachments must be 'ignore', 'reference', or 'download'"
            )
        if max_results is not None and (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results < 1
        ):
            raise ValueError('max_results must be a positive integer')

        labels_ids = [
            lbl.id if isinstance(lbl, Label) else lbl for lbl in labels
        ]
        list_params = {
            'userId': user_id,
            'q': query,
            'labelIds': labels_ids,
            'includeSpamTrash': include_spam_trash,
        }
        if max_results is not None:
            list_params['maxResults'] = min(
                max_results, self._MAX_MESSAGES_PER_PAGE
            )

        response = self.service.users().messages().list(
            **list_params
        ).execute()

        message_refs = list(response.get('messages', []))

        while response.get('nextPageToken') and (
            max_results is None or len(message_refs) < max_results
        ):
            list_params['pageToken'] = response['nextPageToken']
            if max_results is not None:
                list_params['maxResults'] = min(
                    max_results - len(message_refs),
                    self._MAX_MESSAGES_PER_PAGE
                )
            response = self.service.users().messages().list(
                **list_params
            ).execute()

            message_refs.extend(response.get('messages', []))

        return self._get_messages_from_refs(
            user_id,
            message_refs,
            attachments,
            metadata_only=metadata_only
        )

    def list_labels(self, user_id: str = 'me') -> list[Label]:
        """
        Retrieves all labels for the specified user.

        These Label objects are to be used with other functions like
        modify_labels().

        Args:
            user_id: The user's email address. By default, the authenticated
                user.

        Returns:
            The list of Label objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        res = self.service.users().labels().list(userId=user_id).execute()
        return [Label(name=x['name'], id=x['id']) for x in res['labels']]

    def create_label(
        self,
        name: str,
        user_id: str = 'me'
    ) -> Label:
        """
        Creates a new label.

        Args:
            name: The display name of the new label.
            user_id: The user's email address. By default, the authenticated
                user.

        Returns:
            The created Label object.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        body = {
            "name": name,

            # TODO: In the future, can add the following fields:
            # "messageListVisibility"
            # "labelListVisibility"
            # "color"
        }

        res = self.service.users().labels().create(
            userId=user_id,
            body=body
        ).execute()
        return Label(res['name'], res['id'])

    def delete_label(self, label: Label, user_id: str = 'me') -> None:
        """
        Deletes a label.

        Args:
            label: The label to delete.
            user_id: The user's email address. By default, the authenticated
                user.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.service.users().labels().delete(
            userId=user_id,
            id=label.id
        ).execute()

    def _get_messages_from_refs(
        self,
        user_id: str,
        message_refs: list[dict],
        attachments: str = 'reference',
        parallel: bool = True,
        metadata_only: bool = False
    ) -> list[Message]:
        """
        Retrieves the actual messages from a list of references.

        Args:
            user_id: The account the messages belong to.
            message_refs: A list of message references with keys id, threadId.
            attachments: Accepted values are 'ignore' which completely ignores
                all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download'
                which downloads the attachment data to store locally. Default
                'reference'.
            parallel: Whether to retrieve messages in parallel. Default true.
                Small result sets use the current service to avoid worker setup.
            metadata_only: Whether to retrieve headers without message bodies
                or attachments. Default False.


        Returns:
            A list of Message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if not message_refs:
            return []

        target_msgs_per_thread = 10  # empirically chosen
        if not parallel or len(message_refs) <= target_msgs_per_thread:
            return [self._build_message_from_ref(
                        user_id, ref, attachments,
                        metadata_only=metadata_only)
                    for ref in message_refs]

        max_num_threads = 12  # empirically chosen, prevents throttling
        num_threads = min(
            math.ceil(len(message_refs) / target_msgs_per_thread),
            max_num_threads
        )
        batch_size = math.ceil(len(message_refs) / num_threads)

        def download_batch(thread_num):
            gmail = Gmail(credentials=self.creds)
            try:
                start = thread_num * batch_size
                end = min(len(message_refs), (thread_num + 1) * batch_size)
                return [
                    gmail._build_message_from_ref(
                        user_id,
                        message_refs[i],
                        attachments,
                        metadata_only=metadata_only,
                    )
                    for i in range(start, end)
                ]
            finally:
                gmail.service.close()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            batches = executor.map(download_batch, range(num_threads))
            return [message for batch in batches for message in batch]

    def _build_message_from_ref(
        self,
        user_id: str,
        message_ref: dict,
        attachments: str = 'reference',
        metadata_only: bool = False,
    ) -> Message:
        """
        Creates a Message object from a reference.

        Args:
            user_id: The username of the account the message belongs to.
            message_ref: The message reference object returned from the Gmail
                API.
            attachments: Accepted values are 'ignore' which completely ignores
                all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            metadata_only: Whether to retrieve headers without message bodies
                or attachments. Default False.

        Returns:
            The Message object.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        params = {'userId': user_id, 'id': message_ref['id']}
        if metadata_only:
            params['format'] = 'metadata'

        service = self.service
        message = service.users().messages().get(**params).execute()
        msg_id = message['id']
        payload = message['payload']

        date = ''
        sender = ''
        recipient = ''
        subject = ''
        msg_hdrs = {}
        cc = []
        bcc = []
        for header in payload['headers']:
            name = header['name']
            value = header['value']
            normalized_name = name.lower()
            if normalized_name == 'date':
                try:
                    date = str(parser.parse(value).astimezone())
                except (OverflowError, TypeError, ValueError):
                    date = value
            elif normalized_name == 'from':
                sender = value
            elif normalized_name == 'to':
                recipient = value
            elif normalized_name == 'subject':
                subject = value
            elif normalized_name == 'cc':
                cc = [
                    formataddr(address) for address in getaddresses([value])
                ]
            elif normalized_name == 'bcc':
                bcc = [
                    formataddr(address) for address in getaddresses([value])
                ]

            msg_hdrs[name] = value

        parts = [] if metadata_only else self._evaluate_message_payload(
            payload, user_id, msg_id, attachments
        )
        plain_parts = [
            part['body'] for part in parts if part['part_type'] == 'plain'
        ]
        html_parts = [
            part['body'] for part in parts if part['part_type'] == 'html'
        ]
        attms = [
            Attachment(
                service,
                user_id,
                msg_id,
                part['attachment_id'],
                part['filename'],
                part['filetype'],
                part['data'],
            )
            for part in parts
            if part['part_type'] == 'attachment'
        ]

        return Message(
            service,
            self.creds,
            user_id,
            msg_id,
            message['threadId'],
            recipient,
            sender,
            subject,
            date,
            html.unescape(message.get('snippet', '')),
            '\n'.join(plain_parts) if plain_parts else None,
            '<br/>'.join(html_parts) if html_parts else None,
            message.get('labelIds', []),
            attms,
            msg_hdrs,
            cc,
            bcc,
            size_estimate=message.get('sizeEstimate'),
        )

    def _evaluate_message_payload(
        self,
        payload: dict,
        user_id: str,
        msg_id: str,
        attachments: str = 'reference'
    ) -> list[dict]:
        """
        Recursively evaluate a Gmail MIME payload.

        Gmail may store any sufficiently large MIME part behind an
        ``attachmentId``. Text parts without attachment metadata are therefore
        parsed as message bodies even when their bytes require another request.

        Args:
            payload: The message payload object (response from Gmail API).
            user_id: The current account address (default 'me').
            msg_id: The id of the message.
            attachments: Accepted values are 'ignore' which completely ignores
                all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            A list of message parts.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        mime_type = payload.get('mimeType', '')
        body = payload.get('body', {})

        if mime_type.startswith('multipart'):
            ret = []
            for part in payload.get('parts', []):
                ret.extend(self._evaluate_message_payload(
                    part, user_id, msg_id, attachments
                ))
            return ret

        disposition = next((
            header['value'].lower()
            for header in payload.get('headers', [])
            if header['name'].lower() == 'content-disposition'
        ), '')
        attachment_id = body.get('attachmentId')
        is_attachment = (
            bool(payload.get('filename'))
            or disposition.startswith('attachment')
            or (
                not mime_type.startswith('text/')
                and (attachment_id or disposition.startswith('inline'))
            )
        )

        if is_attachment:
            if attachments == 'ignore':
                return []

            obj = {
                'part_type': 'attachment',
                'filetype': mime_type,
                'filename': payload.get('filename') or 'unknown',
                'attachment_id': attachment_id,
                'data': None
            }

            if attachments == 'download' or not attachment_id:
                obj['data'] = self._get_message_part_data(
                    payload, user_id, msg_id
                )
            return [obj]

        if mime_type in ('text/html', 'text/plain'):
            data = self._get_message_part_data(payload, user_id, msg_id)
            headers = MIMEMessage()
            for header in payload.get('headers', []):
                headers[header['name']] = header['value']
            charset = headers.get_content_charset() or 'utf-8'

            if mime_type == 'text/html':
                soup = BeautifulSoup(data, 'lxml', from_encoding=charset)
                return [{
                    'part_type': 'html',
                    'body': str(soup.body or soup),
                }]

            return [{
                'part_type': 'plain',
                'body': data.decode(charset, errors='replace'),
            }]

        return []

    def _get_message_part_data(
        self,
        payload: dict,
        user_id: str,
        msg_id: str,
    ) -> bytes:
        """Return decoded inline or externally stored MIME part data."""

        body = payload.get('body', {})
        data = body.get('data')
        attachment_id = body.get('attachmentId')
        if not data and attachment_id:
            res = self.service.users().messages().attachments().get(
                userId=user_id, messageId=msg_id, id=attachment_id
            ).execute()
            data = res['data']

        return _decode_base64url(data or '')

    def _send_message(self, message: dict, user_id: str) -> Message:
        res = self.service.users().messages().send(
            userId=user_id,
            body=message
        ).execute()
        return self._build_message_from_ref(user_id, res, 'reference')

    def _create_message(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: str | None = None,
        msg_plain: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
        signature: bool = False,
        user_id: str = 'me',
        reply_to: Message | None = None,
    ) -> dict:
        """
        Creates the raw email message to be sent.

        Args:
            sender: The email address the message is being sent from.
            to: The email address the message is being sent to.
            subject: The subject line of the email.
            msg_html: The HTML message of the email.
            msg_plain: The plain text alternate message of the email (for slow
                or old browsers).
            cc: The list of email addresses to be Cc'd.
            bcc: The list of email addresses to be Bcc'd
            attachments: A list of attachment file paths.
            signature: Whether the account signature should be added to the
                message. Will add the signature to your HTML message only, or a
                create a HTML message if none exists.
            reply_to: The message being replied to.

        Returns:
            The message dict.

        """

        msg = MIMEMultipart('mixed' if attachments else 'alternative')
        msg['To'] = to
        msg['From'] = sender

        if reply_to is None:
            msg['Subject'] = subject
        else:
            headers = {
                name.lower(): value
                for name, value in reply_to.headers.items()
            }
            message_id = headers.get('message-id')
            if not reply_to.thread_id:
                raise ValueError('reply_to must have a thread ID')
            if not message_id:
                raise ValueError('reply_to must have a Message-ID header')
            if subject and subject != reply_to.subject:
                raise ValueError('reply subject must match the original')
            references = headers.get('references')
            in_reply_to = headers.get('in-reply-to', '')
            if not references and len(re.findall(
                r'<[^<>]+@[^<>]+>', in_reply_to
            )) == 1:
                references = in_reply_to
            msg['Subject'] = reply_to.subject
            msg['In-Reply-To'] = message_id
            msg['References'] = ' '.join(
                value for value in (references, message_id) if value
            )

        if cc:
            msg['Cc'] = ', '.join(cc)

        if bcc:
            msg['Bcc'] = ', '.join(bcc)

        if signature:
            address = parseaddr(sender)[1] or sender
            account_sig = self._get_alias_info(address, user_id)['signature']

            if msg_html is None:
                msg_html = ''

            msg_html += "<br /><br />" + account_sig

        body = MIMEMultipart('alternative') if attachments else msg

        if msg_plain:
            body.attach(MIMEText(msg_plain, 'plain'))

        if msg_html:
            body.attach(MIMEText(msg_html, 'html'))

        if attachments:
            if msg_plain or msg_html:
                msg.attach(body)

            self._ready_message_with_attachments(msg, attachments)

        message = {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        if reply_to is not None:
            message['threadId'] = reply_to.thread_id

        return message

    def _ready_message_with_attachments(
        self,
        msg: MIMEMultipart,
        attachments: list[str]
    ) -> None:
        """
        Converts attachment filepaths to MIME objects and adds them to msg.

        Args:
            msg: The message to add attachments to.
            attachments: A list of attachment file paths.

        """

        for filepath in attachments:
            content_type, encoding = mimetypes.guess_type(filepath)

            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'

            main_type, sub_type = content_type.split('/', 1)
            with open(filepath, 'rb') as file:
                raw_data = file.read()

            attm = MIMEBase(main_type, sub_type)
            attm.set_payload(raw_data)
            encoders.encode_base64(attm)

            fname = os.path.basename(filepath)
            attm.add_header('Content-Disposition', 'attachment', filename=fname)
            msg.attach(attm)

    def _get_alias_info(
        self,
        send_as_email: str,
        user_id: str = 'me'
    ) -> dict:
        """
        Returns the alias info of an email address on the authenticated
        account.

        Response data is of the following form:
        {
            "sendAsEmail": string,
            "displayName": string,
            "replyToAddress": string,
            "signature": string,
            "isPrimary": boolean,
            "isDefault": boolean,
            "treatAsAlias": boolean,
            "smtpMsa": {
                "host": string,
                "port": integer,
                "username": string,
                "password": string,
                "securityMode": string
            },
            "verificationStatus": string
        }

        Args:
            send_as_email: The alias account information is requested for
                (could be the primary account).
            user_id: The user ID of the authenticated user the account the
                alias is for (default "me").

        Returns:
            The dict of alias info associated with the account.

        """

        req =  self.service.users().settings().sendAs().get(
                   sendAsEmail=send_as_email, userId=user_id)

        res = req.execute()
        return res
