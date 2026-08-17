"""
File: message.py
----------------
This module contains the implementation of the Message object.

"""

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import Resource

from simplegmail import label
from simplegmail.attachment import Attachment
from simplegmail.label import Label


class Message:
    """
    A Gmail message and operations that modify its state.

    Instances are normally returned by Gmail retrieval and sending methods
    rather than constructed directly.

    Args:
        service: The Gmail service object.
        creds: Credentials used to refresh the service when necessary.
        user_id: The account the message belongs to.
        msg_id: The Gmail message ID.
        thread_id: The Gmail thread ID.
        recipient: The message's To header.
        sender: The message's From header.
        subject: The message subject.
        date: The parsed message date, or the original value if parsing failed.
        snippet: The Gmail-generated message preview.
        plain: The plain-text contents of the message. Default None.
        html: the HTML contents of the message. Default None.
        label_ids: Gmail label ID strings associated with the message.
        attachments: Attachments belonging to the message.
        headers: Message headers keyed by their original names.
        cc: Parsed Cc addresses.
        bcc: Parsed Bcc addresses.
        size_estimate: The estimated message size in bytes. Default None.

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        id (str): the message id.
        thread_id (str): the Gmail thread ID.
        recipient (str): who the message was addressed to.
        sender (str): who the message was sent from.
        subject (str): the subject line of the message.
        date (str): the date the message was sent.
        snippet (str): the snippet line for the message.
        plain (str | None): the plaintext contents of the message.
        html (str | None): the HTML contents of the message.
        label_ids (list[str]): the ids of labels associated with this message.
        attachments (list[Attachment]): attachments for the message.
        headers (dict): a dict of header values.
        cc (list[str]): who the message was cc'd on the message.
        bcc (list[str]): who the message was bcc'd on the message.
        size_estimate (int | None): the estimated message size in bytes.

    """

    def __init__(
        self,
        service: Resource,
        creds: Credentials,
        user_id: str,
        msg_id: str,
        thread_id: str,
        recipient: str,
        sender: str,
        subject: str,
        date: str,
        snippet: str,
        plain: str | None = None,
        html: str | None = None,
        label_ids: list[str] | None = None,
        attachments: list[Attachment] | None = None,
        headers: dict | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        size_estimate: int | None = None
    ) -> None:
        self._service = service
        self.creds = creds
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
        self.label_ids = label_ids or []
        self.attachments = attachments or []
        self.headers = headers or {}
        self.cc = cc or []
        self.bcc = bcc or []
        self.size_estimate = size_estimate

    @property
    def service(self) -> Resource:
        if self.creds.expired:
            self.creds.refresh(Request())

        return self._service

    def __repr__(self) -> str:
        """Represents the object by its sender, recipient, and id."""

        return (
            f'Message(to: {self.recipient}, from: {self.sender}, id: {self.id})'
        )

    def mark_as_read(self) -> None:
        """
        Marks this message as read (by removing the UNREAD label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.UNREAD)

    def mark_as_unread(self) -> None:
        """
        Marks this message as unread (by adding the UNREAD label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.UNREAD)

    def mark_as_spam(self) -> None:
        """
        Marks this message as spam (by adding the SPAM label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.SPAM)

    def mark_as_not_spam(self) -> None:
        """
        Marks this message as not spam (by removing the SPAM label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.SPAM)

    def mark_as_important(self) -> None:
        """
        Marks this message as important (by adding the IMPORTANT label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.IMPORTANT)

    def mark_as_not_important(self) -> None:
        """
        Marks this message as not important (by removing the IMPORTANT label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.IMPORTANT)

    def star(self) -> None:
        """
        Stars this message (by adding the STARRED label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.STARRED)

    def unstar(self) -> None:
        """
        Unstars this message (by removing the STARRED label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.STARRED)

    def move_to_inbox(self) -> None:
        """
        Moves an archived message to your inbox (by adding the INBOX label).

        """

        self.add_label(label.INBOX)

    def archive(self) -> None:
        """
        Archives the message (removes from inbox by removing the INBOX label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.INBOX)

    def trash(self) -> None:
        """
        Moves this message to the trash.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.
            RuntimeError: Gmail did not report the message in trash.

        """

        res = self.service.users().messages().trash(
            userId=self.user_id, id=self.id,
        ).execute()
        if label.TRASH not in res.get('labelIds', []):
            raise RuntimeError('An error occurred in a call to `trash`.')

        self.label_ids = res['labelIds']

    def untrash(self) -> None:
        """
        Removes this message from the trash.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.
            RuntimeError: Gmail still reported the message in trash.

        """

        res = self.service.users().messages().untrash(
            userId=self.user_id, id=self.id,
        ).execute()
        if label.TRASH in res.get('labelIds', []):
            raise RuntimeError('An error occurred in a call to `untrash`.')

        self.label_ids = res.get('labelIds', [])

    def move_from_inbox(self, to: Label | str) -> None:
        """
        Moves a message from your inbox to another label "folder".

        Args:
            to: The label to move to.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.
            RuntimeError: Gmail returned labels inconsistent with the request.

        """

        self.modify_labels(to, label.INBOX)

    def add_label(self, to_add: Label | str) -> None:
        """
        Adds the given label to the message.

        Args:
            to_add: The label to add.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_labels([to_add])

    def add_labels(self, to_add: list[Label] | list[str]) -> None:
        """
        Adds the given labels to the message.

        Args:
            to_add: The list of labels to add.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.modify_labels(to_add, [])

    def remove_label(self, to_remove: Label | str) -> None:
        """
        Removes the given label from the message.

        Args:
            to_remove: The label to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_labels([to_remove])

    def remove_labels(self, to_remove: list[Label] | list[str]) -> None:
        """
        Removes the given labels from the message.

        Args:
            to_remove: The list of labels to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.modify_labels([], to_remove)

    def modify_labels(
        self,
        to_add: Label | str | list[Label] | list[str],
        to_remove: Label | str | list[Label] | list[str]
    ) -> None:
        """
        Adds or removes the specified label.

        Args:
            to_add: The label or list of labels to add.
            to_remove: The label or list of labels to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.
            RuntimeError: Gmail returned labels inconsistent with the request.

        """

        if isinstance(to_add, (Label, str)):
            to_add = [to_add]

        if isinstance(to_remove, (Label, str)):
            to_remove = [to_remove]

        body = self._create_update_labels(to_add, to_remove)
        res = self.service.users().messages().modify(
            userId=self.user_id, id=self.id,
            body=body,
        ).execute()

        label_ids = res.get('labelIds', [])
        if (
            not all(lbl in label_ids for lbl in body['addLabelIds'])
            or not all(
                    lbl not in label_ids for lbl in body['removeLabelIds']
            )
        ):
            raise RuntimeError(
                'An error occurred while modifying message label.'
            )

        self.label_ids = label_ids

    def _create_update_labels(
        self,
        to_add: list[Label] | list[str] | None = None,
        to_remove: list[Label] | list[str] | None = None
    ) -> dict:
        """
        Creates an object for updating message label.

        Args:
            to_add: A list of labels to add.
            to_remove: A list of labels to remove.

        Returns:
            The modify labels object to pass to the Gmail API.

        """

        if to_add is None:
            to_add = []

        if to_remove is None:
            to_remove = []

        return {
            'addLabelIds': [
                lbl.id if isinstance(lbl, Label) else lbl for lbl in to_add
            ],
            'removeLabelIds': [
                lbl.id if isinstance(lbl, Label) else lbl for lbl in to_remove
            ]
        }
