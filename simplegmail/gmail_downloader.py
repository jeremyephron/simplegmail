"""
File: gmail_downloader.py
--------------
Class for processing messages into a dataframe, and saving attachments into an attachments folder

"""

import pandas as pd

class GmailDownloader:
    def __init__(self, gmail):
        self.gmail = gmail

    def clean_string(self, s):
        """Replace undesired characters in a string."""
        return s.replace("_", "-").replace(" ", "-").replace("/", "-")

    def process_messages(self, messages):
        """Process messages into a dataframe, and save attachments."""
        data = []
        for c, message in enumerate(messages, start=1):
            # Create a dictionary with the message data
            message_data = {
                'id': message.id,
                'sender': message.sender,
                'recipient': message.recipient,
                'subject': message.subject,
                'plain': message.plain,
                'html': message.html,
                'date': message.date
            }
            data.append(message_data)

            # Save the attachments
            self.save_attachments(message)

        return pd.DataFrame(data)

    def save_attachments(self, message):
        """Save attachments to a folder."""
        if message.attachments:
            for c, attm in enumerate(message.attachments, start=1):
                attm.filename = self.clean_string(attm.filename)
                attm.filetype = self.clean_string(attm.filetype)
                filepath = f"attachments/{message.id}_{c}_{attm.filename}_{attm.filetype}"
                attm.save(filepath=filepath, overwrite=True)