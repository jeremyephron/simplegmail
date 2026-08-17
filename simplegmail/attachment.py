"""
File: attachment.py
-------------------
This module contains the implementation of the Attachment object.

"""

import base64  # for base64.urlsafe_b64decode
import os  # for os.path.exists

from googleapiclient.discovery import Resource


def _decode_base64url(data: str) -> bytes:
    """Decode base64url data whether or not Gmail includes padding."""

    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))


class Attachment:
    """
    An attachment belonging to a Gmail message.

    Instances are normally created by message retrieval methods rather than
    constructed directly.

    Args:
        service: The Gmail service object.
        user_id: The username of the account the message belongs to.
        msg_id: The id of message the attachment belongs to.
        att_id: The Gmail attachment ID, if its data is stored separately.
        filename: The filename associated with the attachment.
        filetype: The mime type of the file.
        data: Raw file data, or None until downloaded.

    Attributes:
        _service (googleapiclient.discovery.Resource): The Gmail service object.
        user_id (str): The username of the account the message belongs to.
        msg_id (str): The id of message the attachment belongs to.
        id (str | None): The Gmail attachment ID, when available.
        filename (str): The filename associated with the attachment.
        filetype (str): The mime type of the file.
        data (bytes | None): Raw file data, or None until downloaded.

    """

    def __init__(
        self,
        service: Resource,
        user_id: str,
        msg_id: str,
        att_id: str | None,
        filename: str,
        filetype: str,
        data: bytes | None = None
    ) -> None:
        self._service = service
        self.user_id = user_id
        self.msg_id = msg_id
        self.id = att_id
        self.filename = filename
        self.filetype = filetype
        self.data = data

    def download(self) -> None:
        """Download the attachment data if it is not already in memory.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if self.data is not None:
            return

        res = self._service.users().messages().attachments().get(
            userId=self.user_id, messageId=self.msg_id, id=self.id
        ).execute()

        self.data = _decode_base64url(res['data'])

    def save(
        self,
        filepath: str | None = None,
        overwrite: bool = False
    ) -> None:
        """Save the attachment, downloading it first if necessary.

        Args:
            filepath: File or existing directory where the attachment should
                be saved. Default None, which uses the stored filename.
            overwrite: Whether to overwrite an existing file. Default False.

        Raises:
            FileExistsError: The destination exists and overwrite is False.

        """
        if filepath is None:
            filepath = self.filename
        elif os.path.isdir(filepath):
            filepath = os.path.join(filepath, os.path.basename(self.filename))

        if not overwrite and os.path.exists(filepath):
            raise FileExistsError(
                f"Cannot overwrite file '{filepath}'. Use overwrite=True if "
                f"you would like to overwrite the file."
            )

        if self.data is None:
            self.download()

        with open(filepath, 'wb') as f:
            f.write(self.data)
