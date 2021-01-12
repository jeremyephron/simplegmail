# simplegmail

A simple Gmail API client in Python for applications.

## New in v3.1.0

Message downloading has been multithreaded resulting in significant speedup of downloads! Make sure to upgrade your installation (no other changes are required).

---

Currently Supported Behavior:
- Sending html messages
- Sending messages with attachments
- Sending messages with your Gmail account signature
- Retrieving messages with the full suite of Gmail's search capabilities
- Retrieving messages with attachments, and downloading attachments
- Modifying message labels (includes marking as read/unread, important/not 
  important, starred/unstarred, trash/untrash, inbox/archive)

## Table of Contents

- [Getting Started](#getting-started)
- [Installation](#installation)
- [Usage](#usage)
    - [Send a simple message](#send-a-simple-message)
    - [Send a message with attachments, cc, bcc fields](#send-a-message-with-attachments-cc-bcc-fields)
    - [Retrieving messages](#retrieving-messages)
    - [Marking messages](#marking-messages)
    - [Changing message labels](#changing-message-labels)
    - [Downloading attachments](#downloading-attachments)
    - [Retrieving messages with queries](#retrieving-messages-advanced-with-queries)
    - [Retrieving messages with more advanced queries](#retrieving-messages-more-advanced-with-more-queries)
- [Feedback](#feedback)

## Getting Started

The only setup required is to download an OAuth 2.0 Client ID file from Google
that will authorize your application.

This can be done at: https://console.developers.google.com/apis/credentials.
For those who haven't created a credential for Google's API, after clicking the 
link above (and logging in to the appropriate account),

1. Select/create the project that this authentication is for (if creating a new 
project make sure to configure the OAuth consent screen; you only need to set 
an Application name)

2. Click on the "Dashboard" tab, then "Enable APIs and Services". Search for 
Gmail and enable.

3. Click on the Credentials tab, then "Create Credentials" > "OAuth client ID".

4. Select what kind of application this is for, and give it a memorable name.
Fill out all necessary information for the credential (e.g., if choosing 
"Web Application" make sure to add an Authorized Redirect URI. See 
https://developers.google.com/identity/protocols/oauth2 for more infomation).

5. Back on the credentials screen, click the download icon next to the 
credential you just created to download it as a JSON object.

6. Save this file as "client_secret.json" and place it in the root directory of 
your application. (The `Gmail` class takes in an argument for the name of this 
file if you choose to name it otherwise.)

The first time you create a new instance of the `Gmail` class, a browser window 
will open, and you'll be asked to give permissions to the application. This 
will save an access token in a file named "gmail-token.json", and only needs to 
occur once.

You are now good to go!

Note about authentication method: I have opted not to use a username-password 
authentication (through imap/smtp), since using Google's authorization is both 
significantly safer and avoids clashing with Google's many security measures.

## Installation

Install using `pip` (Python3).

```bash
pip3 install simplegmail
```

## Usage

### Send a simple message:

```python
from simplegmail import Gmail

gmail = Gmail() # will open a browser window to ask you to log in and authenticate

params = {
  "to": "you@youremail.com",
  "sender": "me@myemail.com",
  "subject": "My first email",
  "msg_html": "<h1>Woah, my first email!</h1><br />This is an HTML email.",
  "msg_plain": "Hi\nThis is a plain text email.",
  "signature": True  # use my account signature
}
message = gmail.send_message(**params)  # equivalent to send_message(to="you@youremail.com", sender=...)
```

### Send a message with attachments, cc, bcc fields:

```python
from simplegmail import Gmail

gmail = Gmail()

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
message = gmail.send_message(**params)  # equivalent to send_message(to="you@youremail.com", sender=...)
```

It couldn't be easier!

### Retrieving messages:

```python
from simplegmail import Gmail

gmail = Gmail()

# Unread messages in your inbox
messages = gmail.get_unread_inbox()

# Starred messages
messages = gmail.get_starred_messages()

# ...and many more easy to use functions can be found in gmail.py!

# Print them out!
for message in messages:
    print("To: " + message.recipient)
    print("From: " + message.sender)
    print("Subject: " + message.subject)
    print("Date: " + message.date)
    print("Preview: " + message.snippet)
    
    print("Message Body: " + message.plain)  # or message.html
```

### Marking messages:

```python
from simplegmail import Gmail

gmail = Gmail()

messages = gmail.get_unread_inbox()

message_to_read = messages[0]
message_to_read.mark_as_read()

# Oops, I want to mark as unread now
message_to_read.mark_as_unread()

message_to_star = messages[1]
message_to_star.star()

message_to_trash = messages[2]
message_to_trash.trash()

# ...and many more functions can be found in message.py!
```

### Changing message labels:

```python
from simplegmail import Gmail

gmail = Gmail()

# Get the label objects for your account. Each label has a specific ID that 
# you need, not just the name!
labels = gmail.list_labels()

# To find a label by the name that you know (just an example):
finance_label = list(filter(lambda x: x.name == 'Finance', labels))[0]

messages = gmail.get_unread_inbox()

# We can add/remove a label
message = messages[0]
message.add_label(finance_label) 

# We can "move" a message from one label to another
message.modify_labels(to_add=labels[10], to_remove=finance_label)

# ...check out the code in message.py for more!
```

### Downloading attachments:

```python
from simplegmail import Gmail

gmail = Gmail()

messages = gmail.get_unread_inbox()

message = messages[0]
if message.attachments:
    for attm in message.attachments:
        print('File: ' + attm.filename)
        attm.save()  # downloads and saves each attachment under it's stored
                     # filename. You can download without saving with `attm.download()`

```

### Retrieving messages (advanced, with queries!):

```python
from simplegmail import Gmail
from simplegmail.query import construct_query

gmail = Gmail()

# Unread messages in inbox with label "Work"
labels = gmail.list_labels()
work_label = list(filter(lambda x: x.name == 'Work', labels))[0]

messages = gmail.get_unread_inbox(labels=[work_label])

# For even more control use queries:
# Messages that are: newer than 2 days old, unread, labeled "Finance" or both "Homework" and "CS"
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

gmail = Gmail()

# For even more control use queries:
# Messages that are either:
#   newer than 2 days old, unread, labeled "Finance" or both "Homework" and "CS"
#     or
#   newer than 1 month old, unread, labeled "Top Secret", but not starred.

labels = gmail.list_labels()

# Construct our two queries separately
query_params_1 = {
    "newer_than": (2, "day"),
    "unread": True,
    "labels":[["Finance"], ["Homework", "CS"]]
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

If there is functionality you'd like to see added, or any bugs in this project,
please let me know by posting an issue or submitting a pull request!
