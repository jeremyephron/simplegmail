"""
Home to the main Gmail service object. Currently supports sending mail (with
attachments) and retrieving mail with the full suite of Gmail search options.

"""

import base64  # for base64.urlsafe_b64decode
# MIME parts for constructing a message
from email.mime.audio       import MIMEAudio
from email.mime.application import MIMEApplication
from email.mime.base        import MIMEBase
from email.mime.image       import MIMEImage
from email.mime.multipart   import MIMEMultipart
from email.mime.text        import MIMEText
import html       # for html.unescape
import mimetypes  # for mimetypes.guesstype
import os         # for os.path.basename

from bs4 import BeautifulSoup  # for parsing email HTML
import dateutil.parser as parser  # for parsing email date
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http
from oauth2client import client, file, tools
from oauth2client.clientsecrets import InvalidClientSecretsError

from simplegmail import labels
from simplegmail.message import Message
from simplegmail.attachment import Attachment


class Gmail(object):
    """
    The Gmail class which serves as the entrypoint for the Gmail service API.

    Args:
        client_secret_file (str): Optional. The name of the user's client
            secret file. Default 'client_secret.json'.

    Attributes:
        service (googleapiclient.discovery.Resource): The Gmail service object.

    """

    # Allow Gmail to read and write emails, and access settings like aliases.
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.settings.basic'
    ]

    # If you don't have a client secret file, follow the instructions at:
    # https://developers.google.com/gmail/api/quickstart/python
    # Make sure the client secret file is in the root directory of your app.
    CLIENT_SECRETS_FILE = 'client_secret.json'
    CREDENTIALS_FILE = 'gmail-token.json'

    def __init__(self, client_secret_file='client_secret.json'):
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
            raise FileNotFoundError(
                "Your 'client_secrets.json' file is nonexistent. Make sure "
                "the file is in the root directory of your application. If "
                "you don't have a client secrets file, go to https://"
                "developers.google.com/gmail/api/quickstart/python, and "
                "follow the instructions listed there."
            )

    def send_message(self, sender, to, subject='', msg_html=None, 
                     msg_plain=None, cc=None, bcc=None, attachments=None,
                     signature=False, user_id='me'):
        """
        Sends an email.

        Args:
            sender (str): The email address the message is being sent from.
            to (str): The email address the message is being sent to.
            subject (str): The subject line of the email. Default ''.
            msg_html (str): The HTML message of the email. Default None.
            msg_plain (str): The plain text alternate message of the email (for
                slow or old browsers). Default None.
            cc (List[str]): The list of email addresses to be Cc'd. Default
                None.
            bcc (List[str]): The list of email addresses to be Bcc'd.
                Default None.
            attachments (List[str]): The list of attachment file names. Default
                None.
            signature (bool): Whether the account signature should be added to
                the message. Default False.
            user_id (str): Optional. The address of the sending account.
                Default 'me'.

        Returns:
            (dict) The dict response of the message if successful.
            (str) "Error" if unsuccessful.

        """

        msg = self._create_message(sender, to, subject, msg_html, msg_plain,
                                   cc=cc, bcc=bcc, attachments=attachments,
                                   signature=signature)

        try:
            req = self.service.users().messages().send(userId='me', body=msg)
            res = req.execute()
            return self._build_message_from_ref(user_id, res, 'reference')

        except HttpError as error:
            print(f"An error has occurred: {error}")
            return "Error"

    def get_unread_inbox(self, user_id='me', label_ids=[], query='',
                         attachments='reference'):
        """
        Gets unread messages from your inbox.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.INBOX)
        return self.get_unread_messages(user_id, label_ids, query)

    def get_starred_messages(self, user_id='me', label_ids=[], query='',
                             attachments='reference', include_spam_trash=False):
        """
        Gets starred messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.STARRED)
        return self.get_messages(user_id, label_ids, query, attachments,
                                 include_spam_trash)

    def get_important_messages(self, user_id='me', label_ids=[], query='',
                               attachments='reference',
                               include_spam_trash=False):
        """
        Gets messages marked important from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.IMPORTANT)
        return self.get_messages(user_id, label_ids, query, attachments, 
                                 include_spam_trash)

    def get_unread_messages(self, user_id='me', label_ids=[], query='',
                            attachments='reference', include_spam_trash=False):
        """
        Gets unread messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): Whether to include messages from spam
                or trash.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.UNREAD)
        return self.get_messages(user_id, label_ids, query, attachments,
                                 include_spam_trash)

    def get_drafts(self, user_id='me', label_ids=[], query='',
                   attachments='reference', include_spam_trash=False):
        """
        Gets drafts saved in your account.

        Args:
            user_id (str): The user's email address [by default, the
                           authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): Whether to include messages from spam
                                       or trash.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.DRAFTS)
        return self.get_messages(user_id, label_ids, query, attachments, 
                                 include_spam_trash)

    def get_sent_messages(self, user_id='me', label_ids=[], query='',
                          attachments='reference', include_spam_trash=False):
        """
        Gets sent messages from your account.

        Args:
            user_id (str): The user's email address [by default, the
                authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): Whether to include messages from spam
                or trash.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.SENT)
        return self.get_messages(user_id, label_ids, query, attachments,
                                 include_spam_trash)

    def get_trash_messages(self, user_id='me', label_ids=[], query='',
                           attachments='reference'):

        """
        Gets messages in your trash from your account.

        Args:
            user_id (str): The user's email address [by default, the
                authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.TRASH)
        return self.get_messages(user_id, label_ids, query, attachments, True)

    def get_spam_messages(self, user_id='me', label_ids=[], query='',
                          attachments='reference'):
        """
        Gets messages marked as spam from your account.

        Args:
            user_id (str): The user's email address [by default, the
                authenticated user].
            label_ids (List[str]): Label IDs messages must match.
            query (str): A Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            List[Message]: a list of message objects.

        """

        label_ids.append(labels.SPAM)
        return self.get_messages(user_id, label_ids, query, attachments, True)

    def get_messages(self, user_id='me', label_ids=[], query='',
                     attachments='reference', include_spam_trash=False):
        """
        Gets messages from your account.

        Args:
            user_id (str): the user's email address. Default 'me', the
                authenticated user.
            label_ids (List[str]): label IDs messages must match.
            query (str): a Gmail query to match.
            attachments (str): accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.
            include_spam_trash (bool): whether to include messages from spam
                or trash.

        Returns:
            List[Message]: a list of message objects.
            
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

            return self._get_messages_from_refs(user_id, message_refs,
                                                attachments)

        except HttpError as error:
            print(f"An error occurred: {error}")

    def _get_messages_from_refs(self, user_id, message_refs,
                                attachments='reference'):
        """
        Retrieves the actual messages from a list of references.

        Args:
            user_id (str): The account the messages belong to.
            message_refs (List[dict]): A list of message references of the form
                                       {id, threadId}.
            attachments (str): Accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            List[Message]: a list of Message objects.

        """

        return [self._build_message_from_ref(user_id, ref, attachments)
                for ref in message_refs]

    def _build_message_from_ref(self, user_id, message_ref,
                                attachments='reference'):
        """
        Creates a Message object from a reference.

        Args:
            user_id (str): the username of the account the message belongs to.
            message_ref (dict): the message reference object return from the 
                Gmail API.
            attachments (str): Accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            Message: the Message object.

        """
        try:
            # Get message JSON
            message = self.service.users().messages().get(
                userId=user_id, id=message_ref['id']
            ).execute()
        
        except HttpError as error:
            print(f'An error occurred while retreiving a message: {error}')

        else:
            msg_id = message['id']
            thread_id = message['threadId']
            label_ids = message['labelIds']
            snippet = html.unescape(message['snippet'])

            payload = message['payload']
            headers = payload['headers']

            # Get header fields (date, from, to, subject)
            date = ''
            sender = ''
            recipient = ''
            subject = ''
            for hdr in headers:
                if hdr['name'] == 'Date':
                    try:
                        date = str(parser.parse(hdr['value']).astimezone())
                    except Exception:
                        date = hdr['value']
                elif hdr['name'] == 'From':
                    sender = hdr['value']
                elif hdr['name'] == 'To':
                    recipient = hdr['value']
                elif hdr['name'] == 'Subject':
                    subject = hdr['value']

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

            return Message(self.service, user_id, msg_id, thread_id, recipient, 
                sender, subject, date, snippet, plain_msg, html_msg, label_ids,
                attms)

    def _evaluate_message_payload(self, payload, user_id, msg_id,
                                  attachments='reference'):
        """
        Recursively evaluates a message payload.

        Args:
            payload (dict): the message payload object (response from Gmail
                API).
            user_id (str): the current account address (default 'me').
            msg_id (str): the id of the message.
            attachments (str): Accepted values are 'ignore' which completely 
                ignores all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            List[dict]: a list of message parts.

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
            body = BeautifulSoup(data, 'lxml').body
            return [{ 'part_type': 'html', 'body': str(body) }]

        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            data = base64.urlsafe_b64decode(data)
            body = data.decode('UTF-8')
            return [{ 'part_type': 'plain', 'body': body }]

        elif payload['mimeType'].startswith('multipart'):
            ret = []
            for part in payload['parts']:
                ret.extend(self._evaluate_message_payload(part, user_id, msg_id,
                                                          attachments))
            return ret

        return []

    def _create_message(self, sender, to, subject='', msg_html=None,
                        msg_plain=None, cc=None, bcc=None, attachments=None,
                        signature=False):
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
                              the message. Will add the signature to your HTML
                              message only, or a create a HTML message if none
                              exists.

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

    def _ready_message_with_attachments(self, msg, attachments):
        """
        Converts attachment filepaths to MIME objects and adds them to msg.

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
