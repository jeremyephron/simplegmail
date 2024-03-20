"""
File: gmail.py
--------------
Revised gmail.py excluding unused functions, and including print counters.

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
from simplegmail.helper import current_hkt_timestamp


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

        c = 0
        
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

            c += len(response['messages'])
            print(f"Processed {c} messages so far from get_messages function at {current_hkt_timestamp()}")

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

        c = 0
        
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

            nonlocal c
            c += len(message_lists[thread_num])
            print(f"Processed {c} messages so far from _get_messages_from_refs function at {current_hkt_timestamp()}")

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
