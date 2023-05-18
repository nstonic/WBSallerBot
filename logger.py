import logging

import telegram


class TGLoggerHandler(logging.Handler):

    def __init__(self, tg_token, chat_id):
        super().__init__()
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=tg_token)

    def emit(self, record):
        self.bot.send_message(
            self.chat_id,
            self.format(record)
        )
