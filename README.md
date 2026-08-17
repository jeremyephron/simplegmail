# simplegmail

[![PyPI downloads](https://img.shields.io/pypi/dm/simplegmail.svg?label=PyPI%20downloads)](https://pypi.org/project/simplegmail/)

A small Python client for sending, retrieving, and modifying messages through
the Gmail API.

simplegmail supports:

- plain-text and HTML messages;
- file attachments, Cc, Bcc, aliases, and Gmail signatures;
- standard-library `EmailMessage` objects, drafts, and threaded replies;
- Gmail search queries and common inbox filters;
- lazy or eager attachment downloads; and
- label changes such as read/unread, star/unstar, archive, spam, and trash.

## Requirements and installation

simplegmail requires Python 3.10 or newer.

```bash
python -m pip install simplegmail
```

## Google OAuth setup

Before using the library, create OAuth desktop credentials for a Google Cloud
project:

1. Create or select a project in the
   [Google Cloud console](https://console.cloud.google.com/).
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth client ID with the application type **Desktop app**.
5. Download the client JSON as `client_secret.json` into your application
   directory.

Google's [Gmail Python quickstart](https://developers.google.com/gmail/api/quickstart/python)
contains the current console instructions.

The first `Gmail()` call opens a browser for authorization and stores the
result in `gmail_token.json`:

```python
from simplegmail import Gmail

gmail = Gmail()
```

Both paths are configurable:

```python
gmail = Gmail(
    client_secret_file="config/client_secret.json",
    creds_file="config/gmail_token.json",
)
```

Treat both files as secrets and never commit them. When an external OAuth app
has the publishing status **Testing**, Google may expire its authorization and
refresh token after seven days. For long-running use, change the consent
screen's publishing status to **Production**, delete the old token file, and
authorize again. See Google's
[OAuth audience documentation](https://support.google.com/cloud/answer/15549945)
for the applicable requirements.

`Gmail(noauth_local_webserver=True)` prints the authorization URL instead of
opening it. Authorization still requires a local callback; Google no longer
supports the old copy-and-paste flow.

Applications can inject existing `google-auth` credentials and skip file-based
authentication:

```python
import json
import os

from google.oauth2.credentials import Credentials
from simplegmail import Gmail

credentials = Credentials.from_authorized_user_info(
    json.loads(os.environ["GMAIL_TOKEN"])
)
gmail = Gmail(credentials=credentials)
```

`GMAIL_TOKEN` is an application-defined environment variable containing the
authorized-user JSON normally stored in `gmail_token.json`.

## Sending messages

Pass at least `sender` and `to`. A message may contain plain text, HTML, or
both:

```python
from simplegmail import Gmail

gmail = Gmail()
message = gmail.send_message(
    sender="me@example.com",
    to="you@example.com",
    subject="Hello",
    msg_plain="Hello from simplegmail.",
    msg_html="<p>Hello from <strong>simplegmail</strong>.</p>",
)
```

Add attachments, Cc, Bcc, or the configured Gmail signature as needed:

```python
message = gmail.send_message(
    sender="Me <me@example.com>",
    to="you@example.com",
    cc=["copy@example.com"],
    bcc=["hidden@example.com"],
    subject="Report",
    msg_plain="The report is attached.",
    attachments=["reports/report.pdf", "images/chart.png"],
    signature=True,
)
```

Attachment bytes are preserved for all MIME types. The type is inferred from
the filename and defaults to `application/octet-stream` when unknown.

### Standard-library EmailMessage

For complete MIME control, construct an `EmailMessage` directly:

```python
from email.message import EmailMessage

from simplegmail import Gmail

email = EmailMessage()
email["To"] = "you@example.com"
email["From"] = "me@example.com"
email["Subject"] = "Custom message"
email.set_content("Built with Python's email package.")

sent = Gmail().send_email_message(email)
```

### Threaded replies

Use `reply_to` to send a response in the original Gmail thread:

```python
original = gmail.get_messages(query='subject:"Original subject"')[0]

reply = gmail.send_message(
    sender="me@example.com",
    to=original.sender,
    msg_plain="Thanks for your message.",
    reply_to=original,
)
```

The original message must have a thread ID and `Message-ID` header. Its subject
is reused because Gmail requires matching subjects when adding a reply to a
thread.

### Drafts

`create_draft()` accepts the same content and attachment options as
`send_message()` and returns the Gmail API draft resource:

```python
draft = gmail.create_draft(
    sender="me@example.com",
    to="you@example.com",
    subject="Work in progress",
    msg_plain="This message is not ready yet.",
)
print(draft["id"])
```

## Retrieving messages

Convenience methods include `get_unread_inbox()`, `get_starred_messages()`,
`get_important_messages()`, `get_unread_messages()`, `get_drafts()`,
`get_sent_messages()`, `get_trash_messages()`, and `get_spam_messages()`.

```python
messages = gmail.get_unread_inbox()

for message in messages:
    print("To:", message.recipient)
    print("From:", message.sender)
    print("Subject:", message.subject)
    print("Date:", message.date)
    print("Preview:", message.snippet)
    print("Body:", message.plain or message.html or "")
```

For full control, use `get_messages()`:

```python
messages = gmail.get_messages(
    labels=["INBOX"],
    query="is:unread",
    attachments="reference",
    include_spam_trash=False,
    max_results=25,
)
```

The relevant options are:

| Option | Behavior |
| --- | --- |
| `labels` | Requires every supplied `Label` object or label ID. |
| `query` | Applies a Gmail search query. |
| `attachments="ignore"` | Omits attachment metadata and data. |
| `attachments="reference"` | Returns attachment metadata and downloads bytes only when requested. This is the default. |
| `attachments="download"` | Downloads all attachment bytes while retrieving messages. |
| `metadata_only=True` | Retrieves headers and size estimates without parsing bodies or attachments. |
| `max_results=N` | Stops after at most `N` matching messages. |
| `include_spam_trash=True` | Includes messages in spam and trash. |
| `user_id` | Selects an account; the default `"me"` means the authenticated account. |

`attachments="download"` retains every downloaded file in memory. Prefer the
default reference mode for large mailboxes or when only selected files are
needed.

`Message.label_ids` is a list of Gmail label ID strings. Use `list_labels()`
when display names or `Label` objects are needed.

## Labels and message state

```python
labels = gmail.list_labels()
finance = next(item for item in labels if item.name == "Finance")

message = gmail.get_unread_inbox()[0]
message.mark_as_read()
message.star()
message.add_label(finance)
message.modify_labels(to_add="IMPORTANT", to_remove=finance)
message.archive()
```

Label mutation methods accept either `Label` objects or Gmail label ID strings.
Other helpers include `mark_as_unread()`, `unstar()`, `mark_as_spam()`,
`mark_as_not_spam()`, `mark_as_important()`, `mark_as_not_important()`,
`move_to_inbox()`, `trash()`, and `untrash()`.

## Attachments

In the default reference mode, `download()` fetches bytes on demand and
`save()` downloads if necessary before writing:

```python
from pathlib import Path

Path("downloads").mkdir(exist_ok=True)
for message in gmail.get_unread_inbox():
    for attachment in message.attachments:
        if Path(attachment.filename).suffix.lower() == ".pdf":
            attachment.save(filepath="downloads")
```

If `filepath` is an existing directory, the stored filename is used safely
within that directory. If it is a file path, that exact path is used. Existing
files raise `FileExistsError` unless `overwrite=True` is passed.

The `spec_attachment` query term described below filters messages containing a
matching attachment; it does not filter `message.attachments` after retrieval.

## Search queries

`construct_query()` translates keyword arguments into Gmail search syntax.
Tuples join values with AND; lists join values with OR. The `labels` term is
special: a flat list requires all labels, while a nested list expresses
alternatives.

```python
from datetime import datetime, timedelta, timezone

from simplegmail.query import construct_query

query = construct_query(
    newer_than=(2, "day"),
    unread=True,
    labels=[["Finance"], ["Homework", "CS"]],
)
messages = gmail.get_messages(query=query, max_results=10)

ten_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
recent = gmail.get_messages(
    query=construct_query(after=int(ten_minutes_ago.timestamp()))
)
```

Prefix a keyword with `exclude_` or pass `False` to negate a boolean term:

```python
query = construct_query(unread=True, exclude_starred=True)
```

Pass multiple dictionaries to OR complete queries:

```python
query = construct_query(
    {"sender": "alerts@example.com", "newer_than": (2, "day")},
    {"labels": ["Top Secret"], "starred": False},
)
messages = gmail.get_messages(query=query)
```

Do not mix query dictionaries and keyword terms in one call. Empty sequence
values and unknown terms raise `ValueError`. See `construct_query()` in
`simplegmail/query.py` for the complete keyword list.

## Errors and resource cleanup

Google API request failures propagate as `googleapiclient.errors.HttpError`.
Invalid local arguments raise `ValueError`, and inconsistent label mutation
responses raise `RuntimeError`.

For a long-lived process, reuse one `Gmail` instance. When finished, its
underlying HTTP service can be closed explicitly:

```python
gmail.service.close()
```

## Upgrading to 5.0

- Python 3.10 or newer is required.
- Authentication uses `google-auth`; legacy `oauth2client` token files with a
  refresh token are migrated when refreshed.
- Browser authorization uses a local callback server; the retired manual
  copy-and-paste flow is unavailable.
- `Message.label_ids` consistently contains Gmail label ID strings.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest
```

Report bugs and request features through
[GitHub Issues](https://github.com/jeremyephron/simplegmail/issues).
