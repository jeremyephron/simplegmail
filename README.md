# simple-gmail

A simple Gmail API client in Python for applications.

Current Supported Behavior:
* Sending html messages
* Sending messages with attachments
* Sending messages with your Gmail account signature
* Retrieving messages with the full suite of Gmail's search capabilities

## Getting Started
The only setup required is to download a "client secrets" file from Google that will allow your applications to do its thing.

Follow the instructions here: https://developers.google.com/gmail/api/quickstart/python.

Name the file you download "client_secrets.json" and place it in the root directory of your application.

You are now good to go!

## Usage
### Send a simple message:
```python
from simplegmail import Gmail

gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

params = {
  "to": "you@youremail.com",
  "sender": "me@myemail.com",
  "subject": "My first email",
  "msg_html": "<h1>Woah, my first email!</h1><br />This is an HTML email.",
  "msg_plain": "Hi\nThis is a plain text email.",
  "signature": True  # use my account signature
}
gmail.send_message(**params)  # equivalent to send_message(to="you@youremail.com", sender=...)
```

### Send a message with attachments, cc, bcc fields:
```python
from simplegmail import Gmail

gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

params = {
  "to": "you@youremail.com",
  "sender": "me@myemail.com",
  "cc": ["bob@bobsemail.com"],
  "bcc": ["marie@gossip.com", "hidden@whereami.com"],
  "subject": "My first email",
  "msg_html": "<h1>Woah, my first email!</h1><br />This is an HTML email.",
  "msg_plain": "Hi\nThis is a plain text email.",
  "attachments": ["path/to/something/cool.pdf", "path/to/image.jpg", "path/to/script.py"],
  "signature": True  # use my account signature
}
gmail.send_message(**params)  # equivalent to send_message(to="you@youremail.com", sender=...)
```

It couldn't be easier!

### Retrieving messages:
```python
from simplegmail import Gmail

gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

# Unread messages in your inbox
messages = gmail.get_unread_inbox()

# Starred messages
messages = gmail.get_starred_messages()

# ...and many more easy to use functions...

# Print them out!
for message in messages:
    print("To: " + message['To'])
    print("From: " + message['From'])
    print("Subject: " + message['Subject'])
    print("Date: " + message['Date'])
    print("Preview: " + message['Snippet'])
    
    # print("Message Body: " + message['Message Body'])
```

### Retrieving messages (advanced, with queries!):
```python
from simplegmail import Gmail
from simplegmail.query import construct_query

gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

# Unread messages in inbox with label "Work"
messages = gmail.get_unread_inbox(label_ids=["Work"])

# For even more control use queries:
# Messages that are: newer than 2 days old, unread, labeled "Work" or both "Homework" and "CS"
query_params = {
    "newer_than": (2, "day"),
    "unread": True,
    "labels":[["Work"], ["Homework", "CS"]]
}

messages = gmail.get_messages(query=construct_query(query_params))

# We could have also accomplished this with
# messages = gmail.get_unread_messages(query=construct_query(newer_than=(2, "day"), labels=[["Work"], ["Homework", "CS"]]))
# There are many, many different ways of achieving the same result with search.
```

### Retrieving messages (more advanced, with more queries!):
```python
from simplegmail import Gmail
from simplegmail.query import construct_query

gmail = Gmail()  # will open a browser window to ask you to log in and authenticate

# For even more control use queries:
# Messages that are either:
#   newer than 2 days old, unread, labeled "Work" or both "Homework" and "CS"
#     or
#   newer than 1 month old, unread, labeled "Top Secret", but not starred.

# Construct our two queries separately
query_params_1 = {
    "newer_than": (2, "day"),
    "unread": True,
    "labels":[["Work"], ["Homework", "CS"]]
}

query_params_2 = {
    "newer_than": (1, "month"),
    "unread": True,
    "labels": ["Top Secret"],
    "starred": True,
    "exclude_starred": True
}

# construct_query() will create both query strings and "or" them together.
messages = gmail.get_messages(query=construct_query(query_params_1, query_params_2))
```

For more on what you can do with queries, read the docstring for `construct_query()` in `query.py`.

## Feedback
If there is functionality you'd like to see added, or any bugs in this project, please let me know by posting an issue or submitting a pull request!
