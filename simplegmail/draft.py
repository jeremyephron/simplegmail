"""
File: draft.py
----------------
This module contains the implementation of the Draft object.

"""

from typing import List, Optional, Union

from httplib2 import Http
from googleapiclient.errors import HttpError

from simplegmail import label
from simplegmail.attachment import Attachment
from simplegmail.label import Label
from simplegmail.message import Message


class Draft(object):
    """
    The Draft class for drafts in your Gmail mailbox. This class should not
    be manually constructed. Contains all information about the associated
    draft.

    Args:
        service: the Gmail service object.
        user_id: the username of the account the draft belongs to.
        id: the draft id.
        message: the message.

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        id (str): the draft id.
        message (Message): the message.

    """

    def __init__(
        self,
        service: 'googleapiclient.discovery.Resource',
        creds: 'oauth2client.client.OAuth2Credentials',
        user_id: str,
        id: str,
        message: Message
    ) -> None:
        self._service = service
        self.creds = creds
        self.user_id = user_id
        self.id = id
        self.message = message

    @property
    def service(self) -> 'googleapiclient.discovery.Resource':
        if self.creds.access_token_expired:
            self.creds.refresh(Http())

        return self._service

    def __repr__(self) -> str:
        """Represents the object by its sender, recipient, and id."""

        return (
            f'Draft(to: {self.recipient}, from: {self.sender}, id: {self.id})'
        )
