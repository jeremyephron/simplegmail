"""
File: gmail.py
--------------
Home to the main Gmail service object. Currently supports sending mail (with
attachments) and retrieving mail with the full suite of Gmail search options.

"""

import base64
from email.mime.audio       import MIMEAudio
from email.mime.application import MIMEApplication
from email.mime.base        import MIMEBase
from email.mime.image       import MIMEImage
from email.mime.multipart   import MIMEMultipart
from email.mime.text        import MIMEText
import html
import math
import mimetypes
import os
import re
import threading
from typing import List, Optional

from bs4 import BeautifulSoup
import dateutil.parser as parser
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http
from oauth2client import client, file, tools
from oauth2client.clientsecrets import InvalidClientSecretsError

from simplegmail import label
from simplegmail.attachment import Attachment
from simplegmail.label import Label
from simplegmail.message import Message


class Gmail(object):
    """
    The Gmail class which serves as the entrypoint for the Gmail service API.

    Args:
        client_secret_file: The path of the user's client secret file.
        creds_file: The path of the auth credentials file (created on first
            call).
        access_type: Whether to request a refresh token for usage without a
            user necessarily present. Either 'online' or 'offline'.

    Attributes:
        client_secret_file (str): The name of the user's client secret file.
        service (googleapiclient.discovery.Resource): The Gmail service object.

    """

    # Allow Gmail to read and write emails, and access settings like aliases.
    _SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.settings.basic'
    ]

    # If you don't have a client secret file, follow the instructions at:
    # https://developers.google.com/gmail/api/quickstart/python
    # Make sure the client secret file is in the root directory of your app.

    def __init__(
        self,
        client_secret_file: str = 'client_secret.json',
        creds_file: str = 'gmail_token.json',
        access_type: str = 'offline',
        noauth_local_webserver: bool = False,
        _creds: Optional[client.OAuth2Credentials] = None,
    ) -> None:
        self.client_secret_file = client_secret_file
        self.creds_file = creds_file

        try:
            # The file gmail_token.json stores the user's access and refresh
            # tokens, and is created automatically when the authorization flow
            # completes for the first time.
            if _creds:
                self.creds = _creds
            else:
                store = file.Storage(self.creds_file)
                self.creds = store.get()

            if not self.creds or self.creds.invalid:
                flow = client.flow_from_clientsecrets(
                    self.client_secret_file, self._SCOPES
                )

                flow.params['access_type'] = access_type
                flow.params['prompt'] = 'consent'

                args = []
                if noauth_local_webserver:
                    args.append('--noauth_local_webserver')

                flags = tools.argparser.parse_args(args)
                self.creds = tools.run_flow(flow, store, flags)

            self._service = build(
                'gmail', 'v1', http=self.creds.authorize(Http()),
                cache_discovery=False
            )

        except InvalidClientSecretsError:
            raise FileNotFoundError(
                "Your 'client_secret.json' file is nonexistent. Make sure "
                "the file is in the root directory of your application. If "
                "you don't have a client secrets file, go to https://"
                "developers.google.com/gmail/api/quickstart/python, and "
                "follow the instructions listed there."
            )

    @property
    def service(self) -> 'googleapiclient.discovery.Resource':
        # Since the token is only used through calls to the service object,
        # this ensure that the token is always refreshed before use.
        if self.creds.access_token_expired:
            self.creds.refresh(Http())

        return self._service

    def send_message(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: Optional[str] = None,
        msg_plain: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        signature: bool = False,
        user_id: str = 'me'
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

        Returns:
            The Message object representing the sent message.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        msg = self._create_message(
            sender, to, subject, msg_html, msg_plain, cc=cc, bcc=bcc,
            attachments=attachments, signature=signature, user_id=user_id
        )

        try:
            req = self.service.users().messages().send(userId='me', body=msg)
            res = req.execute()
            return self._build_message_from_ref(user_id, res, 'reference')

        except HttpError as error:
            # Pass along the error
            raise error

    def get_unread_inbox(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.INBOX)
        return self.get_unread_messages(user_id, labels, query)

    def get_starred_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.STARRED)
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_important_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.IMPORTANT)
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_unread_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.UNREAD)
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_drafts(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.DRAFT)
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_sent_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        if labels is None:
            labels = []

        labels.append(label.SENT)
        return self.get_messages(user_id, labels, query, attachments,
                                 include_spam_trash)

    def get_trash_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> List[Message]:

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

        if labels is None:
            labels = []

        labels.append(label.TRASH)
        return self.get_messages(user_id, labels, query, attachments, True)

    def get_spam_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference'
    ) -> List[Message]:
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


        if labels is None:
            labels = []

        labels.append(label.SPAM)
        return self.get_messages(user_id, labels, query, attachments, True)

    def get_messages(
        self,
        user_id: str = 'me',
        labels: Optional[List[Label]] = None,
        query: str = '',
        attachments: str = 'reference',
        include_spam_trash: bool = False
    ) -> List[Message]:
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

        Returns:
            A list of message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if labels is None:
            labels = []

        labels_ids = [
            lbl.id if isinstance(lbl, Label) else lbl for lbl in labels
        ]

        try:
            response = self.service.users().messages().list(
                userId=user_id,
                q=query,
                labelIds=labels_ids,
                includeSpamTrash=include_spam_trash
            ).execute()

            message_refs = []
            if 'messages' in response:  # ensure request was successful
                message_refs.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = self.service.users().messages().list(
                    userId=user_id,
                    q=query,
                    labelIds=labels_ids,
                    includeSpamTrash=include_spam_trash,
                    pageToken=page_token
                ).execute()

                message_refs.extend(response['messages'])

            return self._get_messages_from_refs(user_id, message_refs,
                                                attachments)

        except HttpError as error:
            # Pass along the error
            raise error

    def list_labels(self, user_id: str = 'me') -> List[Label]:
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

        try:
            res = self.service.users().labels().list(
                userId=user_id
            ).execute()

        except HttpError as error:
            # Pass along the error
            raise error

        else:
            labels = [Label(name=x['name'], id=x['id']) for x in res['labels']]
            return labels

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

        try:
            res = self.service.users().labels().create(
                userId=user_id,
                body=body
            ).execute()

        except HttpError as error:
            # Pass along the error
            raise error

        else:
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

        try:
            self.service.users().labels().delete(
                userId=user_id,
                id=label.id
            ).execute()

        except HttpError as error:
            # Pass along the error
            raise error

    def _get_messages_from_refs(
        self,
        user_id: str,
        message_refs: List[dict],
        attachments: str = 'reference',
        parallel: bool = True
    ) -> List[Message]:
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
                Currently parallelization is always on, since there is no
                reason to do otherwise.


        Returns:
            A list of Message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if not message_refs:
            return []

        if not parallel:
            return [self._build_message_from_ref(user_id, ref, attachments)
                    for ref in message_refs]

        max_num_threads = 12  # empirically chosen, prevents throttling
        target_msgs_per_thread = 10  # empirically chosen
        num_threads = min(
            math.ceil(len(message_refs) / target_msgs_per_thread),
            max_num_threads
        )
        batch_size = math.ceil(len(message_refs) / num_threads)
        message_lists = [None] * num_threads

        def thread_download_batch(thread_num):
            gmail = Gmail(_creds=self.creds)

            start = thread_num * batch_size
            end = min(len(message_refs), (thread_num + 1) * batch_size)
            message_lists[thread_num] = [
                gmail._build_message_from_ref(
                    user_id, message_refs[i], attachments
                )
                for i in range(start, end)
            ]

            gmail.service.close()

        threads = [
            threading.Thread(target=thread_download_batch, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        return sum(message_lists, [])

    def _build_message_from_ref(
        self,
        user_id: str,
        message_ref: dict,
        attachments: str = 'reference'
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

        Returns:
            The Message object.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        try:
            # Get message JSON
            message = self.service.users().messages().get(
                userId=user_id, id=message_ref['id']
            ).execute()

        except HttpError as error:
            # Pass along the error
            raise error

        else:
            msg_id = message['id']
            thread_id = message['threadId']
            label_ids = []
            if 'labelIds' in message:
                user_labels = {x.id: x for x in self.list_labels(user_id=user_id)}
                label_ids = [user_labels[x] for x in message['labelIds']]
            snippet = html.unescape(message['snippet'])

            payload = message['payload']
            headers = payload['headers']

            # Get header fields (date, from, to, subject)
            date = ''
            sender = ''
            recipient = ''
            subject = ''
            msg_hdrs = {}
            cc = []
            bcc = []
            for hdr in headers:
                if hdr['name'].lower() == 'date':
                    try:
                        date = str(parser.parse(hdr['value']).astimezone())
                    except Exception:
                        date = hdr['value']
                elif hdr['name'].lower() == 'from':
                    sender = hdr['value']
                elif hdr['name'].lower() == 'to':
                    recipient = hdr['value']
                elif hdr['name'].lower() == 'subject':
                    subject = hdr['value']
                elif hdr['name'].lower() == 'cc':
                    cc = hdr['value'].split(', ')
                elif hdr['name'].lower() == 'bcc':
                    bcc = hdr['value'].split(', ')

                msg_hdrs[hdr['name']] = hdr['value']

            parts = self._evaluate_message_payload(
                payload, user_id, message_ref['id'], attachments
            )

            plain_msg = None
            html_msg = None
            attms = []
            for part in parts:
                if part['part_type'] == 'plain':
                    if plain_msg is None:
                        plain_msg = part['body']
                    else:
                        plain_msg += '\n' + part['body']
                elif part['part_type'] == 'html':
                    if html_msg is None:
                        html_msg = part['body']
                    else:
                        html_msg += '<br/>' + part['body']
                elif part['part_type'] == 'attachment':
                    attm = Attachment(self.service, user_id, msg_id,
                                      part['attachment_id'], part['filename'],
                                      part['filetype'], part['data'])
                    attms.append(attm)

            return Message(
                self.service,
                self.creds,
                user_id,
                msg_id,
                thread_id,
                recipient,
                sender,
                subject,
                date,
                snippet,
                plain_msg,
                html_msg,
                label_ids,
                attms,
                msg_hdrs,
                cc,
                bcc
            )

    def _evaluate_message_payload(
        self,
        payload: dict,
        user_id: str,
        msg_id: str,
        attachments: str = 'reference'
    ) -> List[dict]:
        """
        Recursively evaluates a message payload.

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

        if 'attachmentId' in payload['body']:  # if it's an attachment
            if attachments == 'ignore':
                return []

            att_id = payload['body']['attachmentId']
            filename = payload['filename']
            if not filename:
                filename = 'unknown'

            obj = {
                'part_type': 'attachment',
                'filetype': payload['mimeType'],
                'filename': filename,
                'attachment_id': att_id,
                'data': None
            }

            if attachments == 'reference':
                return [obj]

            else:  # attachments == 'download'
                if 'data' in payload['body']:
                    data = payload['body']['data']
                else:
                    res = self.service.users().messages().attachments().get(
                        userId=user_id, messageId=msg_id, id=att_id
                    ).execute()
                    data = res['data']

                file_data = base64.urlsafe_b64decode(data)
                obj['data'] = file_data
                return [obj]

        elif payload['mimeType'] == 'text/html':
            data = payload['body']['data']
            data = base64.urlsafe_b64decode(data)
            body = BeautifulSoup(data, 'lxml', from_encoding='utf-8').body
            return [{ 'part_type': 'html', 'body': str(body) }]

        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            data = base64.urlsafe_b64decode(data)
            body = data.decode('UTF-8')
            return [{ 'part_type': 'plain', 'body': body }]

        elif payload['mimeType'].startswith('multipart'):
            ret = []
            if 'parts' in payload:
                for part in payload['parts']:
                    ret.extend(self._evaluate_message_payload(part, user_id, msg_id,
                                                              attachments))
            return ret

        return []

    def _create_message(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: str = None,
        msg_plain: str = None,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[str] = None,
        signature: bool = False,
        user_id: str = 'me'
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

        Returns:
            The message dict.

        """

        msg = MIMEMultipart('mixed' if attachments else 'alternative')
        msg['To'] = to
        msg['From'] = sender
        msg['Subject'] = subject

        if cc:
            msg['Cc'] = ', '.join(cc)

        if bcc:
            msg['Bcc'] = ', '.join(bcc)

        if signature:
            m = re.match(r'.+\s<(?P<addr>.+@.+\..+)>', sender)
            address = m.group('addr') if m else sender
            account_sig = self._get_alias_info(address, user_id)['signature']

            if msg_html is None:
                msg_html = ''

            msg_html += "<br /><br />" + account_sig

        attach_plain = MIMEMultipart('alternative') if attachments else msg
        attach_html = MIMEMultipart('related') if attachments else msg

        if msg_plain:
            attach_plain.attach(MIMEText(msg_plain, 'plain'))

        if msg_html:
            attach_html.attach(MIMEText(msg_html, 'html'))

        if attachments:
            attach_plain.attach(attach_html)
            msg.attach(attach_plain)

            self._ready_message_with_attachments(msg, attachments)

        return {
            'raw': base64.urlsafe_b64encode(msg.as_string().encode()).decode()
        }

    def _ready_message_with_attachments(
        self,
        msg: MIMEMultipart,
        attachments: List[str]
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

                attm: MIMEBase
                if main_type == 'text':
                    attm = MIMEText(raw_data.decode('UTF-8'), _subtype=sub_type)
                elif main_type == 'image':
                    attm = MIMEImage(raw_data, _subtype=sub_type)
                elif main_type == 'audio':
                    attm = MIMEAudio(raw_data, _subtype=sub_type)
                elif main_type == 'application':
                    attm = MIMEApplication(raw_data, _subtype=sub_type)
                else:
                    attm = MIMEBase(main_type, sub_type)
                    attm.set_payload(raw_data)

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
