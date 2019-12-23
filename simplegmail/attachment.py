"""
This module contains the implementation of the Attachment object.

"""

import base64  # for base64.urlsafe_b64decode
import os      # for os.path.exists

class Attachment(object):
    """
    The Attachment class for attachments to emails in your Gmail mailbox. This 
    class should not be manually instantiated.

    Args:
        service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        msg_id (str): the id of message the attachment belongs to.
        att_id (str): the id of the attachment.
        filename (str): the filename associated with the attachment.
        filetype (str): the mime type of the file.
        data (bytes): the raw data of the file. Default None.

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        msg_id (str): the id of message the attachment belongs to.
        id (str): the id of the attachment.
        filename (str): the filename associated with the attachment.
        filetype (str): the mime type of the file.
        data (bytes): the raw data of the file.

    """
    
    def __init__(self, service, user_id, msg_id, att_id, filename, filetype,
                 data=None):
        self._service = service
        self.user_id = user_id
        self.msg_id = msg_id
        self.id = att_id
        self.filename = filename
        self.filetype = filetype
        self.data = data

    def download(self):
        """
        Downloads the data for an attachment if it does not exist.
        
        """
        
        if self.data is not None:
            return

        res = self._service.users().messages().attachments().get(
            userId=self.user_id, messageId=self.msg_id, id=self.id
        ).execute()

        data = res['data']
        self.data = base64.urlsafe_b64decode(data)

    def save(self, filepath=None, overwrite=False):
        """
        Saves the attachment. Downloads file data if not downloaded.
        
        Args:
            filepath (str): where to save the attachment. Default None, which 
                uses the filename stored.
            overwrite (bool): whether to overwrite existing files. Default False.
        
        Raises:
            FileExistsError: if the call would overwrite an existing file and 
                overwrite is not set to True.
        """
        
        if filepath is None:
            filepath = self.filename

        if self.data is None:
            self.download()

        if overwrite and os.path.exists(filepath):
            raise FileExistsError(
                f"Cannot overwrite file '{filepath}'. Use overwrite=True if "
                f"you would like to overwrite the file."
            )

        with open(filepath, 'wb') as f:
            f.write(self.data)

