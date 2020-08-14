"""Gmail reserved system labels."""

from dataclasses import dataclass


@dataclass
class Label:
    name: str
    id: str


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

