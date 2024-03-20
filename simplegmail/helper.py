from datetime import datetime
import pytz

# Getting current timestamp for print counters
def current_hkt_timestamp():
    hkt_time = datetime.now(pytz.timezone('Asia/Hong_Kong')) # change for other timezones
    return hkt_time.strftime('%Y-%m-%d %H:%M:%S')