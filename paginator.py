import more_itertools
from telegram import InlineKeyboardButton


class Paginator:

    def __init__(self, item_list: list, page_size: int = 10):
        self.item_list = item_list
        self.items_count = len(item_list)
        self.page_size = page_size
        self.pages = list(more_itertools.chunked(self.item_list, self.page_size))
        self.total_pages = len(self.pages)
        self.is_paginated = self.total_pages > 1
        self.max_page_number = self.total_pages - 1

    def get_keyboard(
            self,
            main_menu_button: InlineKeyboardButton,
            page_number: int = 0,
            callback_data_prefix: str = ''
    ) -> list[list[InlineKeyboardButton]]:
        page_number = min(max(0, page_number), self.total_pages)
        keyboard_menu_buttons = [main_menu_button]
        if self.max_page_number >= page_number > 0:
            keyboard_menu_buttons.insert(
                0,
                InlineKeyboardButton(
                    f'< {page_number}/{self.total_pages}',
                    callback_data=f'page_{page_number - 1}'
                )
            )
        if page_number < self.max_page_number:
            keyboard_menu_buttons.append(
                InlineKeyboardButton(
                    f'{page_number + 2}/{self.total_pages} >',
                    callback_data=f'page_{page_number + 1}'
                )
            )
        keyboard = [
            [InlineKeyboardButton(
                item.get_button_text(),
                callback_data=f'{callback_data_prefix}{item.get_callback_data()}'
            )]
            for item in self.pages[page_number]
        ]
        keyboard.append(keyboard_menu_buttons)
        return keyboard
