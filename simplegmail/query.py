"""
File: query.py
--------------
This module contains functions for constructing Gmail search queries.

"""

from typing import List, Union


def construct_query(*query_dicts, **query_terms) -> str:
    """
    Constructs a query from either:

    (1) a list of dictionaries representing queries to "or" (only one of the
        queries needs to match). Each of these dictionaries should be made up
        of keywords as specified below.

        E.g.:
        construct_query(
          {'sender': 'someone@email.com', 'subject': 'Meeting'},
          {'sender': ['boss@inc.com', 'hr@inc.com'], 'newer_than': (5, "day")}
        )

        Will return a query which matches all messages that either match the
        all the fields in the first dictionary or match all the fields in the
        second dictionary.

    -- OR --

    (2) Keyword arguments specifying individual query terms (each keyword will
        be and'd).


    To negate any term, set it as the value of "exclude_<keyword>" instead of
    "<keyword>" (for example, since `labels=['finance', 'bills']` will match
    messages with both the 'finance' and 'bills' labels,
    `exclude_labels=['finance', 'bills']` will exclude messages that have both
    labels. To exclude either you must specify
    `exclude_labels=[['finance'], ['bills']]`, which negates
    '(finance OR bills)'.

    For all keywords whose values are not booleans, you can indicate you'd
    like to "and" multiple values by placing them in a tuple (), or "or"
    multiple values by placing them in a list [].

    Keyword Arguments:
        sender (str): Who the message is from.
            E.g.: sender='someone@email.com'
                  sender=['john@doe.com', 'jane@doe.com'] # OR

        recipient (str): Who the message is to.
            E.g.: recipient='someone@email.com'

        subject (str): The subject of the message. E.g.: subject='Meeting'

        labels (List[str]): Labels applied to the message (all must match).
            E.g.: labels=['Work', 'HR'] # Work AND HR
                  labels=[['Work', 'HR'], ['Home']] # (Work AND HR) OR Home

        attachment (bool): The message has an attachment. E.g.: attachment=True

        spec_attachment (str): The message has an attachment with a
            specific name or file type.
            E.g.: spec_attachment='pdf',
                  spec_attachment='homework.docx'

        exact_phrase (str): The message contains an exact phrase.
             E.g.: exact_phrase='I need help'
                   exact_phrase=('help me', 'homework') # AND

        cc (str): Recipient in the cc field. E.g.: cc='john@email.com'

        bcc (str): Recipient in the bcc field. E.g.: bcc='jane@email.com'

        before (str): The message was sent before a date.
            E.g.: before='2004/04/27'

        after (str): The message was sent after a date.
            E.g.: after='2004/04/27'

        older_than (Tuple[int, str]): The message was sent before a given
            time period.
            E.g.: older_than=(3, "day")
                  older_than=(1, "month")
                  older_than=(2, "year")

        newer_than (Tuple[int, str]): The message was sent after a given
            time period.
            E.g.: newer_than=(3, "day")
                  newer_than=(1, "month")
                  newer_than=(2, "year")

        near_words (Tuple[str, str, int]): The message contains two words near
            each other. (The third item is the max number of words between the
            two words). E.g.: near_words=('CS', 'hw', 5)

        starred (bool): The message was starred. E.g.: starred=True

        snoozed (bool): The message was snoozed. E.g.: snoozed=True

        unread (bool): The message is unread. E.g.: unread=True

        read (bool): The message has been read. E.g.: read=True

        important (bool): The message was marked as important.
            E.g.: important=True

        drive (bool): The message contains a Google Drive attachment.
            E.g.: drive=True

        docs (bool): The message contains a Google Docs attachment.
            E.g.: docs=True

        sheets (bool): The message contains a Google Sheets attachment.
            E.g.: sheets=True

        slides (bool): The message contains a Google Slides attachment.
            E.g.: slides=True

        list (str): The message is from a mailing list.
            E.g.: list=info@example.com

        in (str): The message is in a folder.
            E.g.: in=anywhere
                  in=chats
                  in=trash

        delivered_to (str): The message was delivered to a given address.
            E.g.: deliveredto=username@gmail.com

        category (str): The message is in a given category.
            E.g.: category=primary

        larger (str): The message is larger than a certain size in bytes.
            E.g.: larger=10M

        smaller (str): The message is smaller than a certain size in bytes
            E.g.: smaller=10M

        id (str): The message has a given message-id header.
            E.g.: id=339376385@example.com

        has (str): The message has a given attribute.
            E.g.: has=userlabels
                  has=nouserlabels

            Note: Labels are only added to a message, and not an entire
            conversation.

    Returns:
        The query string.

    """

    if query_dicts:
        return _or([construct_query(**query) for query in query_dicts])

    terms = []
    for key, val in query_terms.items():
        exclude = False
        if key.startswith('exclude'):
            exclude = True
            key = key[len('exclude_'):]

        query_fn = globals()[f"_{key}"]
        conjunction = _and if isinstance(val, tuple) else _or

        if key in ['newer_than', 'older_than', 'near_words']:
            if isinstance(val[0], (tuple, list)):
                term = conjunction([query_fn(*v) for v in val])
            else:
                term = query_fn(*val)

        elif key == 'labels':
            if isinstance(val[0], (tuple, list)):
                term = conjunction([query_fn(labels) for labels in val])
            else:
                term = query_fn(val)

        elif isinstance(val, (tuple, list)):
            term = conjunction([query_fn(v) for v in val])

        else:
            term = query_fn(val) if not isinstance(val, bool) else query_fn()

        if exclude:
            term = _exclude(term)

        terms.append(term)

    return _and(terms)


def _and(queries: List[str]) -> str:
    """
    Returns a query term matching the "and" of all query terms.

    Args:
        queries: A list of query terms to and.

    Returns:
        The query string.

    """

    if len(queries) == 1:
        return queries[0]

    return f'({" ".join(queries)})'


def _or(queries: List[str]) -> str:
    """
    Returns a query term matching the "or" of all query terms.

    Args:
        queries: A list of query terms to or.

    Returns:
        The query string.

    """

    if len(queries) == 1:
        return queries[0]

    return '{' + ' '.join(queries) + '}'


def _exclude(term: str) -> str:
    """
    Returns a query term excluding messages that match the given query term.

    Args:
        term: The query term to be excluded.

    Returns:
        The query string.

    """

    return f'-{term}'


def _sender(sender: str) -> str:
    """
    Returns a query term matching "from".

    Args:
        sender: The sender of the message.

    Returns:
        The query string.

    """

    return f'from:{sender}'


def _recipient(recipient: str) -> str:
    """
    Returns a query term matching "to".

    Args:
        recipient: The recipient of the message.

    Returns:
        The query string.

    """

    return f'to:{recipient}'


def _subject(subject: str) -> str:
    """
    Returns a query term matching "subject".

    Args:
        subject: The subject of the message.

    Returns:
        The query string.

    """

    return f'subject:{subject}'


def _labels(labels: Union[List[str], str]) -> str:
    """
    Returns a query term matching a multiple labels.

    Works with a single label (str) passed in, instead of the expected list.

    Args:
        labels: A list of labels the message must have applied.

    Returns:
        The query string.

    """

    if isinstance(labels, str):  # called the wrong function
        return _label(labels)

    return _and([_label(label) for label in labels])


def _label(label: str) -> str:
    """
    Returns a query term matching a label.

    Args:
        label: The label the message must have applied.

    Returns:
        The query string.

    """

    return f'label:{label}'


def _spec_attachment(name_or_type: str) -> str:
    """
    Returns a query term matching messages that have attachments with a
    certain name or file type.

    Args:
        name_or_type: The specific name of file type to match.

    Returns:
        The query string.

    """

    return f'filename:{name_or_type}'


def _exact_phrase(phrase: str) -> str:
    """
    Returns a query term matching messages that have an exact phrase.

    Args:
        phrase: The exact phrase to match.

    Returns:
        The query string.

    """

    return f'"{phrase}"'


def _starred() -> str:
    """Returns a query term matching messages that are starred."""

    return 'is:starred'


def _snoozed() -> str:
    """Returns a query term matching messages that are snoozed."""

    return 'is:snoozed'


def _unread() -> str:
    """Returns a query term matching messages that are unread."""

    return 'is:unread'


def _read() -> str:
    """Returns a query term matching messages that are read."""

    return 'is:read'


def _important() -> str:
    """Returns a query term matching messages that are important."""

    return 'is:important'


def _cc(recipient: str) -> str:
    """
    Returns a query term matching messages that have certain recipients in
    the cc field.

    Args:
        recipient: The recipient in the cc field to match.

    Returns:
        The query string.

    """

    return f'cc:{recipient}'


def _bcc(recipient: str) -> str:
    """
    Returns a query term matching messages that have certain recipients in
    the bcc field.

    Args:
        recipient: The recipient in the bcc field to match.

    Returns:
        The query string.

    """

    return f'bcc:{recipient}'


def _after(date: str) -> str:
    """
    Returns a query term matching messages sent after a given date.

    Args:
        date: The date messages must be sent after.

    Returns:
        The query string.

    """

    return f'after:{date}'


def _before(date: str) -> str:
    """
    Returns a query term matching messages sent before a given date.

    Args:
        date: The date messages must be sent before.

    Returns:
        The query string.

    """

    return f'before:{date}'


def _older_than(number: int, unit: str) -> str:
    """
    Returns a query term matching messages older than a time period.

    Args:
        number: The number of units of time of the period.
        unit: The unit of time: "day", "month", or "year".

    Returns:
        The query string.

    """

    return f'older_than:{number}{unit[0]}'


def _newer_than(number: int, unit: str) -> str:
    """
    Returns a query term matching messages newer than a time period.

    Args:
        number: The number of units of time of the period.
        unit: The unit of time: 'day', 'month', or 'year'.

    Returns:
        The query string.

    """

    return f'newer_than:{number}{unit[0]}'


def _near_words(
    first: str,
    second: str,
    distance: int,
    exact: bool = False
) -> str:
    """
    Returns a query term matching messages that two words within a certain
    distance of each other.

    Args:
        first: The first word to search for.
        second: The second word to search for.
        distance: How many words apart first and second can be.
        exact: Whether first must come before second [default False].

    Returns:
        The query string.

    """

    query = f'{first} AROUND {distance} {second}'
    if exact:
        query = '"' + query + '"'

    return query


def _attachment() -> str:
    """Returns a query term matching messages that have attachments."""

    return 'has:attachment'


def _drive() -> str:
    """
    Returns a query term matching messages that have Google Drive attachments.

    """

    return 'has:drive'


def _docs() -> str:
    """
    Returns a query term matching messages that have Google Docs attachments.

    """

    return 'has:document'


def _sheets() -> str:
    """
    Returns a query term matching messages that have Google Sheets attachments.

    """

    return 'has:spreadsheet'


def _slides() -> str:
    """
    Returns a query term matching messages that have Google Slides attachments.

    """

    return 'has:presentation'


def _list(list_name: str) -> str:
    """
    Returns a query term matching messages from a mailing list.

    Args:
        list_name: The name of the mailing list.

    Returns:
        The query string.

    """

    return f'list:{list_name}'


def _in(folder_name: str) -> str:
    """
    Returns a query term matching messages from a folder.

    Args:
        folder_name: The name of the folder.

    Returns:
        The query string.

    """

    return f'in:{folder_name}'


def _delivered_to(address: str) -> str:
    """
    Returns a query term matching messages delivered to an address.

    Args:
        address: The email address the messages are delivered to.

    Returns:
        The query string.

    """

    return f'deliveredto:{address}'


def _category(category: str) -> str:
    """
    Returns a query term matching messages belonging to a category.

    Args:
        category: The category the messages belong to.

    Returns:
        The query string.

    """

    return f'category:{category}'


def _larger(size: str) -> str:
    """
    Returns a query term matching messages larger than a certain size.

    Args:
        size: The minimum size of the messages in bytes. Suffixes are allowed,
            e.g., "10M".

    Returns:
        The query string.

    """

    return f'larger:{size}'


def _smaller(size: str) -> str:
    """
    Returns a query term matching messages smaller than a certain size.

    Args:
        size: The maximum size of the messages in bytes. Suffixes are allowed,
            e.g., "10M".

    Returns:
        The query string.

    """

    return f'smaller:{size}'


def _id(message_id: str) -> str:
    """
    Returns a query term matching messages with the message ID.

    Args:
        message_id: The RFC822 message ID.

    Returns:
        The query string.

    """

    return f'rfc822msgid:{message_id}'


def _has(attribute: str) -> str:
    """
    Returns a query term matching messages with an attribute.

    Args:
        attribute: The attribute of the messages. E.g., "nouserlabels".

    Returns:
        The query string.

    """

    return f'has:{attribute}'
