import pandas as pd
from datetime import datetime, timedelta
from simplegmail import Gmail
from simplegmail import GmailDownloader

# Function to generate monthly date ranges
def month_range(start_date, end_date):
    current_date = start_date
    while current_date < end_date:
        # Calculate the end of the month for the current_date
        month_end = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        # If the month_end is greater than the current date, use the current date instead
        if month_end > datetime.now():
            month_end = datetime.now()
        yield current_date, month_end
        # Set the next current_date to the day after the month_end
        current_date = month_end + timedelta(days=1)

# Define the date range for processing
start_date = datetime(2024, 2, 1)  # Start from Feb 1, 2024
end_date = datetime.now()  # Up to the current date

# Initialize downloader
gmail = Gmail()
gmail_download = GmailDownloader(gmail)

# DataFrame to hold all emails
df_all_emails = pd.DataFrame()

# Loop over each month and process messages
for start, end in month_range(start_date, end_date):
    query = f'after:{start.strftime("%Y/%m/%d")} before:{end.strftime("%Y/%m/%d")}'
    print(query)
    messages = gmail.get_messages(query=query, attachments='download', include_spam_trash=True)
    df_email = gmail_download.process_messages(messages)
    df_all_emails = pd.concat([df_all_emails, df_email])
    print(f"df_all_emails shape is {df_all_emails.shape}")