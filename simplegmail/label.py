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

    Attributes:
        name (str): The name of the Label.
        id (str): The ID of the label.

    """

    def __init__(self, name: str, id: str) -> None:
        self.name = name
        self.id = id

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


INBOX      = Label('INBOX', 'INBOX')
SPAM       = Label('SPAM', 'SPAM')
TRASH      = Label('TRASH', 'TRASH')
UNREAD     = Label('UNREAD', 'UNREAD')
STARRED    = Label('STARRED', 'STARRED')
SENT       = Label('SENT', 'SENT')
IMPORTANT  = Label('IMPORTANT', 'IMPORTANT')
DRAFT      = Label('DRAFT', 'DRAFT')
PERSONAL   = Label('CATEGORY_PERSONAL', 'CATEGORY_PERSONAL')
SOCIAL     = Label('CATEGORY_SOCIAL', 'CATEGORY_SOCIAL')
PROMOTIONS = Label('CATEGORY_PROMOTIONS', 'CATEGORY_PROMOTIONS')
UPDATES    = Label('CATEGORY_UPDATES', 'CATEGORY_UPDATES')
FORUMS     = Label('CATEGORY_FORUMS', 'CATEGORY_FORUMS')
