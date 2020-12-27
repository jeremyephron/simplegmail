"""
File: query.py
--------------
This module contains functions for constructing Gmail search queries.

"""

def construct_query(*query_dicts, **query_terms):
    """
    Constructs a query from either:

    (1) a list of dictionaries representing queries to "or"
        (only one of the queries needs to match). Each of these dictionaries
        should be made up of keywords as specified below.

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


    To negate any term, add a term "exclude_<keyword>" and set it's value
    to True. (for example, `starred=True, exclude_starred=True` will
    exclude all starred messages).

    For all keywords whose values are not booleans, you can indicate you'd
    like to "and" multiple values by placing them in a tuple (), or "or"
    multiple values by placing them in a list [].

    Keyword Arguments:
        sender (str): Who the message is from.
                      E.g.: sender='someone@email.com'
                            sender=['john@doe.com', 'jane@doe.com'] # or

        recipient (str): Who the message is to.
                         E.g.: recipient='someone@email.com'

        subject (str): The subject of the message.
                       E.g.: subject='Meeting'

        labels (List[str]): Labels applied to the message (all must match).
                            E.g.: labels=['Work', 'HR']
                                  labels=[['Work', 'HR'], ['Home']] # or

        attachment (bool): The message has an attachment.
                           E.g.: attachment=True

        spec_attachment (str): The message has an attachment with a
                               specific name or file type.
                               E.g.: spec_attachment='pdf'
                                     spec_attachment='homework.docx'

        exact_phrase (str): The message contains an exact phrase.
                            E.g.: exact_phrase='I need help'
                                  exact_phrase=('help me', 'homework') # and

        cc (str): Recipient in the cc field.
                  E.g.: cc='john@email.com'

        bcc (str): Recipient in the bcc field.
                   E.g.: bcc='jane@email.com'

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

        near_words (Tuple[str, str, int]): The message contains two words
                                           near each other. (The third item
                                           is the max number of words
                                           between the two words).
                                           E.g.: near_words=('CS', 'hw', 5)

        starred (bool): The message was starred.
                        E.g.: starred=True

        snoozed (bool): The message was snoozed.
                        E.g.: snoozed=True

        unread (bool): The message is unread.
                       E.g.: unread=True

        read (bool): The message has been read.
                     E.g.: read=True

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

    Returns:
        The query string.

    """

    if query_dicts:
        return _or([construct_query(**query) for query in query_dicts])

    terms = []
    for key, val in query_terms.items():
        if key.startswith('exclude'):
            continue

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

        if f'exclude_{key}' in query_terms:
            term = _exclude(term)

        terms.append(term)

    return _and(terms)


def _and(queries):
    """
    Returns a query item matching the "and" of all query items.

    Args:
        queries (List[str]): A list of query terms to and.

    Returns:
        The query string.

    """

    if len(queries) == 1:
        return queries[0]

    return f"({' '.join(queries)})"


def _or(queries):
    """
    Returns a query item matching the "or" of all query items.

    Args:
        queries (List[str]): A list of query terms to or.

    Returns:
        The query string.

    """

    if len(queries) == 1:
        return queries[0]

    return "{" + ' '.join(queries) + "}"


def _exclude(term):
    """
    Returns a query item excluding messages that match the given query term.

    Args:
        term (str): The query term to be excluded.

    Returns:
        The query string.

    """

    return f"-{term}"


def _sender(sender):
    """
    Returns a query item matching "from".

    Args:
        sender (str): The sender of the message.

    Returns:
        The query string.

    """

    return f"from:{sender}"


def _recipient(recipient):
    """
    Returns a query item matching "to".

    Args:
        recipient (str): The recipient of the message.

    Returns:
        The query string.

    """

    return f"to:{recipient}"


def _subject(subject):
    """
    Returns a query item matching "subject".

    Args:
        subject: The subject of the message.

    Returns:
        The query string.

    """

    return f"subject:{subject}"

def _labels(labels):
    """
    Returns a query item matching a multiple labels.

    Works with a single label (str) passed in, instead of the expected list.

    Args:
        labels (List[str]): A list of labels the message must have applied.

    Returns:
        The query string.

    """

    if isinstance(labels, str):  # called the wrong function
        return _label(labels)

    return _and([_label(label) for label in labels])

def _label(label):
    """
    Returns a query item matching a label.

    Args:
        label (str): The label the message must have applied.

    Returns:
        The query string.

    """

    return f"label:{label}"


def _spec_attachment(name_or_type):
    """
    Returns a query item matching messages that have attachments with a
    certain name or file type.

    Args:
        name_or_type (str): The specific name of file type to match.


    Returns:
        The query string.

    """

    return f"filename:{name_or_type}"


def _exact_phrase(phrase):
    """
    Returns a query item matching messages that have an exact phrase.

    Args:
        phrase (str): The exact phrase to match.


    Returns:
        The query string.

    """

    return f'"{phrase}"'


def _starred():
    """Returns a query item matching messages that are starred."""

    return f"is:starred"


def _snoozed():
    """Returns a query item matching messages that are snoozed."""

    return f"is:snoozed"


def _unread():
    """Returns a query item matching messages that are unread."""

    return f"is:unread"


def _read():
    """Returns a query item matching messages that are read."""

    return f"is:read"


def _important():
    """Returns a query item matching messages that are important."""

    return f"is:important"


def _cc(recipient):
    """
    Returns a query item matching messages that have certain recipients in
    the cc field.

    Args:
        recipient (str): The recipient in the cc field to match.

    Returns:
        The query string.

    """

    return f"cc:{recipient}"


def _bcc(recipient):
    """
    Returns a query item matching messages that have certain recipients in
    the bcc field.

    Args:
        recipient (str): The recipient in the bcc field to match.

    Returns:
        The query string.

    """

    return f"bcc:{recipient}"


def _after(date):
    """
    Returns a query item matching messages sent after a given date.

    Args:
        date (str): The date messages must be sent after.

    Returns:
        The query string.

    """

    return f"after:{date}"


def _before(date):
    """
    Returns a query item matching messages sent before a given date.

    Args:
        date (str): The date messages must be sent before.

    Returns:
        The query string.

    """

    return f"before:{date}"


def _older_than(number, unit):
    """
    Returns a query item matching messages older than a time period.

    Args:
        number (int): The number of units of time of the period.
        unit (str): The unit of time: "day", "month", or "year".

    Returns:
        The query string.

    """

    return f"older_than:{number}{unit[0]}"


def _newer_than(number, unit):
    """
    Returns a query item matching messages newer than a time period.

    Args:
        number (int): The number of units of time of the period.
        unit (str): The unit of time: "day", "month", or "year".

    Returns:
        The query string.

    """

    return f"newer_than:{number}{unit[0]}"


def _near_words(first, second, distance, exact=False):
    """
    Returns a query item matching messages that two words within a certain
    distance of each other.

    Args:
        first (str): The first word to search for.
        second (str): The second word to search for.
        distance (int): How many words apart first and second can be.
        exact (bool): Whether first must come before second [default False].

    Returns:
        The query string.

    """

    query = f"{first} AROUND {distance} {second}"
    if exact:
        query = '"' + query + '"'

    return query


def _attachment():
    """Returns a query item matching messages that have attachments."""

    return f"has:attachment"


def _drive():
    """
    Returns a query item matching messages that have Google Drive attachments.

    """

    return f"has:drive"


def _docs():
    """
    Returns a query item matching messages that have Google Docs attachments.

    """

    return f"has:document"


def _sheets():
    """
    Returns a query item matching messages that have Google Sheets attachments.

    """

    return f"has:spreadsheet"


def _slides():
    """
    Returns a query item matching messages that have Google Slides attachments.

    """

    return f"has:presentation"
