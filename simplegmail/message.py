"""This module contains the implementation of the Message object."""

from googleapiclient.errors import HttpError

from simplegmail import labels


class Message(object):
    """
    The Message class for emails in your Gmail mailbox. This class should not be
    manually instantiated. Contains all information about the associated 
    message, and can be used to modify the message's labels (e.g., marking as
    read/unread, archiving, moving to trash, starring, etc.).

    Args:
        service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        msg_id (str): the message id.
        thread_id (str): the thread id.
        recipient (str): who the message was addressed to.
        sender (str): who the message was sent from.
        subject (str): the subject line of the message.
        date (str): the date the message was sent.
        snippet (str): the snippet line for the message.
        plain (str): the plaintext contents of the message. Default None.
        html (str): the HTML contents of the message. Default None.
        label_ids (List[str]): the ids of labels associated with this message.
            Default [].
        attachments (List[Attachment]): a list of attachments for the message.
            Default [].

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        id (str): the message id.
        recipient (str): who the message was addressed to.
        sender (str): who the message was sent from.
        subject (str): the subject line of the message.
        date (str): the date the message was sent.
        snippet (str): the snippet line for the message.
        plain (str): the plaintext contents of the message.
        html (str): the HTML contents of the message.
        label_ids (List[str]): the ids of labels associated with this message.
        attachments (List[Attachment]): a list of attachments for the message.

    """
    
    def __init__(self, service, user_id, msg_id, thread_id, recipient, sender,
                 subject, date, snippet, plain=None, html=None, label_ids=[],
                 attachments=[]):
        self._service = service
        self.user_id = user_id
        self.id = msg_id
        self.thread_id = thread_id
        self.recipient = recipient
        self.sender = sender
        self.subject = subject
        self.date = date
        self.snippet = snippet
        self.plain = plain
        self.html = html
        self.label_ids = label_ids
        self.attachments = attachments

    def mark_as_read(self):
        """Marks this message as read (by removing the UNREAD label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_remove=[labels.UNREAD])
            ).execute()
        
        except HttpError as error:
            print(f'An error occurred: {error}')
        
        else:
            assert labels.UNREAD not in res['labelIds'], \
                f'An error occurred in a call to `mark_as_read`.'

            self.label_ids = res['labelIds']

    def mark_as_unread(self):
        """Marks this message as unread (by adding the UNREAD label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add=[labels.UNREAD])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.UNREAD in res['labelIds'], \
                f'An error occurred in a call to `mark_as_unread`.'

            self.label_ids = res['labelIds']

    def mark_as_spam(self):
        """Marks this message as spam (by adding the SPAM label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add=[labels.SPAM])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.SPAM in res['labelIds'], \
                f'An error occurred in a call to `mark_as_spam()`'

            self.label_ids = res['labelIds']

    def mark_as_not_spam(self):
        """Marks this message as not spam (by removing the SPAM label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_remove=[labels.SPAM])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.SPAM not in res['labelIds'], \
                f'An error occurred in a call to `mark_as_not_spam()`'

            self.label_ids = res['labelIds']

    def mark_as_important(self):
        """Marks this message as important (by adding the IMPORTANT label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add=[labels.IMPORTANT])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.IMPORTANT in res['labelIds'], \
                f'An error occurred in a call to `mark_as_important()`'

            self.label_ids = res['labelIds']

    def mark_as_not_important(self):
        """
        Marks this message as not important (by removing the IMPORTANT label).

        """

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_remove=[labels.IMPORTANT])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.IMPORTANT not in res['labelIds'], \
                f'An error occurred in a call to `mark_as_not_important()`'

            self.label_ids = res['labelIds']

    def star(self):
        """Stars this message (by adding the STARRED label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add=[labels.STARRED])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.STARRED in res['labelIds'], \
                f'An error occurred in a call to `star()`'

            self.label_ids = res['labelIds']

    def unstar(self):
        """Unstars this message (by removing the STARRED label)."""

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_remove=[labels.STARRED])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.STARRED not in res['labelIds'], \
                f'An error occurred in a call to `unstar()`'

            self.label_ids = res['labelIds']

    def move_to_inbox(self):
        """
        Moves an archived message to your inbox (by adding the INBOX label).

        """

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add=[labels.INBOX])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.INBOX in res['labelIds'], \
                f'An error occurred in a call to `move_to_inbox()`'

            self.label_ids = res['labelIds']

    def archive(self):
        """
        Archives the message (removes from inbox by removing the INBOX label).

        """

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_remove=[labels.INBOX])
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.INBOX not in res['labelIds'], \
                f'An error occurred in a call to `archive()`'

            self.label_ids = res['labelIds']

    def trash(self):
        """Moves this message to the trash."""

        try:
            res = self._service.users().messages().trash(
                userId=self.user_id, id=self.id,
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.TRASH in res['labelIds'], \
                f'An error occurred in a call to `trash`.'

            self.label_ids = res['labelIds']
    
    def untrash(self):
        """Removes this message from the trash."""

        try:
            res = self._service.users().messages().untrash(
                userId=self.user_id, id=self.id,
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert labels.TRASH not in res['labelIds'], \
                f'An error occurred in a call to `untrash`.'

            self.label_ids = res['labelIds']

    def add_labels(self, to_add):
        """
        Adds the given labels to the message.

        Args:
            to_add (List[str]): the list of label IDs to add.

        """
        
        self.modify_labels(to_add, [])
    
    def remove_labels(self, to_remove):
        """
        Removes the given labels from the message.

        Args:
            to_remove (List[str]): the list of label IDs to remove.

        """

        self.modify_labels([], to_remove)

    def modify_labels(self, to_add, to_remove):
        """
        Adds or removes the specified labels.
        
        Args:
            to_add (List[str]): the list of label IDs to add.
            to_remove (List[str]): the list of label IDs to remove.

        """

        try:
            res = self._service.users().messages().modify(
                userId=self.user_id, id=self.id,
                body=self._create_update_labels(to_add, to_remove)
            ).execute()

        except HttpError as error:
            print(f'An error occurred: {error}')

        else:
            assert all([lbl in res['labelIds'] for lbl in to_add]) \
                and all([lbl not in res['labelIds'] for lbl in to_remove]), \
                'An error occurred while modifying message labels.'
                
            self.label_ids = res['labelIds']

    def _create_update_labels(self, to_add=[], to_remove=[]):
        """
        Creates an object for updating message labels.

        Args:
            to_add (List[str]): a list of label IDs to add.
            to_remove (List[str]): a list of label IDs to remove.

        Returns:
            dict: the modify labels object to pass to the Gmail API.

        """
        
        return {
            'addLabelIds': to_add,
            'removeLabelIds': to_remove
        }
