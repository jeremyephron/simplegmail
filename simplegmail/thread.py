"""
File: thread.py
----------------
This module contains the implementation of the Thread object.

"""

from typing import List, Optional, Union

from httplib2 import Http
from googleapiclient.errors import HttpError

from simplegmail import label
from simplegmail.attachment import Attachment
from simplegmail.label import Label
from simplegmail.message import Message


class Thread(object):
    """
    The Thread class for threads in your Gmail mailbox. This class should not
    be manually constructed. Contains all information about the associated
    thread.

    Args:
        service: the Gmail service object.
        user_id: the username of the account the thread belongs to.
        id: the thread id.
        snippet: the snippet line for the thread.
        messages: a list of message.

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        id (str): the thread id.
        snippet (str): the snippet line for the thread.
        messages (List[Message]): a list of messages.

    """

    def __init__(
        self,
        service: 'googleapiclient.discovery.Resource',
        creds: 'oauth2client.client.OAuth2Credentials',
        user_id: str,
        id: str,
        snippet: str,
        messages: List[Message]
    ) -> None:
        self._service = service
        self.creds = creds
        self.user_id = user_id
        self.id = id
        self.snippet = snippet
        self.messages = messages

    @property
    def service(self) -> 'googleapiclient.discovery.Resource':
        if self.creds.access_token_expired:
            self.creds.refresh(Http())

        return self._service

    def __repr__(self) -> str:
        """Represents the object by its id."""

        return (
            f'Thread(id: {self.id})'
        )
