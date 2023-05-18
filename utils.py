from datetime import datetime

import pytz

from config import TIME_ZONE


def convert_to_created_ago(created_at: datetime) -> str:
    created_ago = datetime.now().astimezone(pytz.timezone(TIME_ZONE)) - \
                  created_at.astimezone(pytz.timezone(TIME_ZONE))
    hours, seconds = divmod(created_ago.seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}'
