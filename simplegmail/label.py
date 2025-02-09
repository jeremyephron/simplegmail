"""
File: label.py
--------------
Gmail reserved system labels and the Label class.

"""


class Label:
    """
    A Gmail label object.

    This class should not typically be constructed directly but rather returned
    from Gmail.list_labels().

    Args:
        name: The name of the Label.
        id: The ID of the label.
        type: The owner type for the label.
        messageListVisibility: The visibility of messages with this label.
        labelListVisibility: The visibility of the label.

    Attributes:
        name (str): The name of the Label.
        id (str): The ID of the label.
        type (str): The owner type for the label.
        messageListVisibility (str): The visibility of messages with this label.
        labelListVisibility (str): The visibility of the label.

    """

    def __init__(
            self, name: str,
            id: str,
            type: str,
            messageListVisibility: str,
            labelListVisibility: str
        ) -> None:
        self.name = name
        self.id = id
        self.type = type
        self.messageListVisibility = messageListVisibility
        self.labelListVisibility = labelListVisibility

    def __repr__(self) -> str:
        return f'Label(name={self.name!r}, id={self.id!r})'

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            # Can be compared to a string of the label ID
            return self.id == other
        elif isinstance(other, Label):
            return self.id == other.id
        else:
            return False


INBOX      = Label('INBOX', 'INBOX', 'system', '', '')
SPAM       = Label('SPAM', 'SPAM', 'system', '', '')
TRASH      = Label('TRASH', 'TRASH', 'system', '', '')
UNREAD     = Label('UNREAD', 'UNREAD', 'system', '', '')
STARRED    = Label('STARRED', 'STARRED', 'system', '', '')
SENT       = Label('SENT', 'SENT', 'system', '', '')
IMPORTANT  = Label('IMPORTANT', 'IMPORTANT', 'system', '', '')
DRAFT      = Label('DRAFT', 'DRAFT', 'system', '', '')
CHAT       = Label('CHAT', 'CHAT', 'system', '', '')
PERSONAL   = Label('CATEGORY_PERSONAL', 'CATEGORY_PERSONAL', 'system', '', '')
SOCIAL     = Label('CATEGORY_SOCIAL', 'CATEGORY_SOCIAL', 'system', '', '')
PROMOTIONS = Label('CATEGORY_PROMOTIONS', 'CATEGORY_PROMOTIONS', 'system', '', '')
UPDATES    = Label('CATEGORY_UPDATES', 'CATEGORY_UPDATES', 'system', '', '')
FORUMS     = Label('CATEGORY_FORUMS', 'CATEGORY_FORUMS', 'system', '', '')
