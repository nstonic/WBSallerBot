from datetime import datetime


def convert_to_created_ago(created_at: datetime) -> str:
    created_ago = datetime.now().timestamp() - created_at.timestamp()
    hours, seconds = divmod(int(created_ago), 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02.0f}ч. {minutes:02.0f}м.'
