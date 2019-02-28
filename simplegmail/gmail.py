"""
Home to the main Gmail service object. Currently supports sending mail (with
attachments) and retrieving mail with the full suite of Gmail search options.

"""

import base64
from datetime import datetime  # for processing email date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
import json  # for pretty printing out json objects
import mimetypes
import os

from bs4 import BeautifulSoup  # for parsing email HTML
import dateutil.parser as parser  # for parsing email date
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http
from oauth2client import client, file, tools
from oauth2client.clientsecrets import InvalidClientSecretsError

from simplegmail import labels

class Gmail(object):

    # Allow Gmail to read and write emails, and access settings like aliases.
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
              'https://www.googleapis.com/auth/gmail.settings.basic']

    # If you don't have a client secret file, follow the instructions at:
    # https://developers.google.com/gmail/api/quickstart/python
    # Make sure the client secret file is in the root directory of your app.
    CLIENT_SECRETS_FILE = 'client_secrets.json'
    CREDENTIALS_FILE = 'gmail-token.json'

    def __init__(self):
        try:
            # The file gmail-token.json stores the user's access and refresh
            # tokens, and is created automatically when the authorization flow
            # completes for the first time.
            store = file.Storage(self.CREDENTIALS_FILE)
            creds = store.get()

            if not creds or creds.invalid:

                # Will ask you to authenticate an account in your browser.
                flow = client.flow_from_clientsecrets(self.CLIENT_SECRETS_FILE,
                                                      self.SCOPES)
                creds = tools.run_flow(flow, store)

            self.service = build('gmail', 'v1', http=creds.authorize(Http()))

        except InvalidClientSecretsError:
            raise Exception("Your 'client_secrets.json' file is nonexistent. "
                            "Make sure the file is in the root directory of "
                            "your application. If you don't have a client "
                            "secrets file, go to https://developers.google.com"
                            "/gmail/api/quickstart/python, and follow the "
                            "instructions listed there.")

    def send_message(self, sender, to, subject, msg_html, msg_plain, cc=None,
                     bcc=None, attachments=None, signature=True):
        """
        Sends an email.

        Args:
            sender (str): The email address the message is being sent from.
            to (str): The email address the message is being sent to.
            subject (str): The subject line of the email.
            msg_html (str): The HTML message of the email.
            msg_plain (str): The plain text alternate message of the email (for
                             slow or old browsers).
            cc (list): The list of email addresses to be Cc'd.
            bcc (list): The list of email addresses to be Bcc'd
            attachments (list): The list of attachment file names.
            signature (bool): Whether the account signature should be added to
                              the message.

        Returns:
            The dict response of the message if successful, "Error" otherwise.

        """


        msg = self._create_message(sender, to, subject, msg_html, msg_plain,
                                   cc=cc, bcc=bcc, attachments=attachments,
                                   signature=signature)

        try:
            req = self.service.users().messages().send(userId='me', body=msg)
            res = req.execute()
            return res

        except HttpError as error:
            print(f"An error has occurred: {error}")
            return "Error"

    def get_unread_inbox(self, user_id='me', label_ids=[], query=''):
        """
        Gets unread messages from your inbox.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.INBOX)
        return self.get_unread_messages(user_id, label_ids, query)

    def get_starred_messages(self, user_id='me', label_ids=[], query='',
                             include_spam_trash=False):
        """
        Gets starred messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.STARRED)
        return self.get_messages(user_id, label_ids, query, include_spam_trash)

    def get_important_messages(self, user_id='me', label_ids=[], query='',
                               include_spam_trash=False):
        """
        Gets messages marked important from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.IMPORTANT)
        return self.get_messages(user_id, label_ids, query, include_spam_trash)

    def get_unread_messages(self, user_id='me', label_ids=[], query='',
                            include_spam_trash=False):
        """
        Gets unread messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.UNREAD)
        return self.get_messages(user_id, label_ids, query, include_spam_trash)

    def get_drafts(self, user_id='me', label_ids=[], query='',
                   include_spam_trash=False):
        """
        Gets drafts saved in your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.DRAFTS)
        return self.get_messages(user_id, label_ids, query, include_spam_trash)

    def get_sent_messages(self, user_id='me', label_ids=[], query='',
                          include_spam_trash=False):
        """
        Gets sent messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.SENT)
        return self.get_messages(user_id, label_ids, query, include_spam_trash)

    def get_trash_messages(self, user_id='me', label_ids=[], query=''):
        """
        Gets messages in your trash from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.TRASH)
        return self.get_messages(user_id, label_ids, query, True)

    def get_spam_messages(self, user_id='me', label_ids=[], query=''):
        """
        Gets messages marked as spam from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        label_ids.append(labels.SPAM)
        return self.get_messages(user_id, label_ids, query, True)

    def get_messages(self, user_id='me', label_ids=[], query='',
                     include_spam_trash=False):
        """
        Gets messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        try:
            response = self.service.users().messages().list(
                userId=user_id,
                q=query,
                labelIds=label_ids
            ).execute()

            message_refs = []
            if 'messages' in response:  # ensure request was successful
                message_refs.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = self.service.users().messages().list(
                    userId=user_id,
                    q=query,
                    labelIds=label_ids,
                    pageToken=page_token
                ).execute()

                message_refs.extend(response['messages'])

            return self._get_messages_from_refs(user_id, message_refs)

        except HttpError as error:
            print(f"An error occurred: {error}")

    # The functionality of this function is a little janky...
    def _get_messages_from_refs(self, user_id, message_refs):
        """
        Retrieves the actual messages from a list of references, constructs a
        dictionary for each message, and returns the final list.

        Args:
            user_id (str): The account the messages belong to.
            message_refs (List[dict]): A list of message references of the form
                                       {id, threadId}.

        Returns:
            A list of dictionaries representing messages with fields:
            { To, From, Subject, Date, Snippet, Message Body }.

        """

        messages = []

        # Download each message in the reference list.
        for ref in message_refs:
            msg_dict = {}

            message = self.service.users().messages().get(
                userId=user_id, id=ref['id']
            ).execute()

            payload = message['payload']
            headers = payload['headers']

            # Get header fields.
            for hdr in headers:
                if hdr['name'] in ['Subject', 'From', 'To']:
                    msg_dict[hdr['name']] = hdr['value']

                elif hdr['name'] == 'Date':
                    try:
                        date = parser.parse(hdr['value']).date()
                    except Exception:
                        date = hdr['value']

                    msg_dict['Date'] = str(date)

            # Get message snippet.
            msg_dict['Snippet'] = message['snippet']

            # Get message body.
            try:
                msg_part = payload
                while msg_part['mimeType'].startswith('multipart'):
                    candidate = msg_part['parts'][0]
                    if not candidate['mimeType'].startswith('multipart'):

                        # Try to find plain text.
                        for part in msg_part['parts']:
                            if part['mimeType'].startswith('text/plain'):
                                msg_part = part
                                break;
                        else:

                            # If there's no plain text, try to find HTML.
                            for part in msg_part['parts']:
                                if part['mimeType'].startswith('text/html'):
                                    msg_part = part
                                    break;

                    else:
                        msg_part = candidate


                data = msg_part['body']['data']

                # Clean the data.
                # Decoding from Base64 to UTF-8
                data = data.replace('-', '+')
                data = data.replace('_', '/')
                data = base64.b64decode(bytes(data, 'UTF-8'))

                # Parsing the message body.
                if msg_part['mimeType'].startswith('text/plain'):
                    msg_body = data.decode("utf-8")

                else:
                    msg_body = BeautifulSoup(data, 'lxml').body

                msg_body = str(msg_body)

                # Clean body.
                msg_body = msg_body.replace('&#39;', "'")
                msg_body = msg_body.replace('&amp;', '&')
                msg_body = msg_body.replace('&lt;', '<')
                msg_body = msg_body.replace('&gt;', '>')
                msg_body = msg_body.replace('\xa0', ' ')
                msg_body = msg_body.replace('\r', '')

                msg_dict['Message Body'] = msg_body

                messages.append(msg_dict)

            except Exception as error:
                print(f"Error: {error} for message:\n"
                      f"{json.dumps(message, indent=4)}")

        return messages

    def _create_message(self, sender, to, subject, msg_html, msg_plain,
                        cc=None, bcc=None, attachments=None, signature=True):
        """
        Creates the raw email message to be sent.

        Args:
            sender (str): The email address the message is being sent from.
            to (str): The email address the message is being sent to.
            subject (str): The subject line of the email.
            msg_html (str): The HTML message of the email.
            msg_plain (str): The plain text alternate message of the email (for
                             slow or old browsers).
            cc (List[str]): The list of email addresses to be Cc'd.
            bcc (List[str]): The list of email addresses to be Bcc'd
            signature (bool): Whether the account signature should be added to
                              the message.

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
            account_sig = self._get_alias_info(sender, 'me')['signature']
            msg_html += "<br /><br />" + account_sig

        attach_plain = MIMEMultipart('alternative') if attachments else msg
        attach_html = MIMEMultipart('related') if attachments else msg

        attach_html.attach(MIMEText(msg_html, 'html'))
        attach_plain.attach(MIMEText(msg_plain, 'plain'))

        if attachments:
            attach_plain.attach(attach_html)
            msg.attach(attach_plain)

            self._ready_message_with_attachments(msg, attachments)

        return {
            'raw': base64.urlsafe_b64encode(msg.as_string().encode()).decode()
        }

    def _ready_message_with_attachments(self, msg, attachments):
        """
        Converts attachment filepaths to MIME objects and adds them to the msg.

        Args:
            msg (MIMEMultipart): The message to add attachments to.
            attachments (List[str]): A list of attachment file paths.

        """

        for filepath in attachments:
            content_type, encoding = mimetypes.guess_type(filepath)

            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'

            main_type, sub_type = content_type.split('/', 1)
            with open(filepath, 'rb') as file:
                raw_data = file.read()
                attm = (MIMEText(raw_data.decode("utf-8"), _subtype=sub_type)
                        if main_type == 'text'

                        else MIMEImage(raw_data, _subtype=sub_type)
                        if main_type == 'image'

                        else MIMEAudio(raw_data, _subtype=sub_type)
                        if main_type == 'audio'

                        else None)

                if not attm:
                    attm = MIMEBase(main_type, sub_type)
                    attm.set_payload(file.read())

            filename = os.path.basename(filepath)
            attm.add_header('Content-Disposition', 'attachment',
                            filename=filename)
            msg.attach(attm)

    def _get_alias_info(self, send_as_email, user_id="me"):
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
            send_as_email (str): The alias account information is requested for
                                 (could be the primary account).
            user_id (str): The user ID of the authenticated user the
                           account the alias is for (default "me").

        """

        req =  self.service.users().settings().sendAs().get(
                   sendAsEmail=send_as_email, userId=user_id)

        res = req.execute()
        return res
