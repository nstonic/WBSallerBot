from dataclasses import dataclass

import more_itertools
from telegram import InlineKeyboardButton


@dataclass
class PaginatorItem:
    callback_data: str
    button_text: str


class Paginator:

    def __init__(self, item_list: list[PaginatorItem], page_size: int = 10):
        self.item_list = item_list
        self.items_count = len(item_list)
        self.page_size = page_size
        self.pages = list(more_itertools.chunked(self.item_list, self.page_size))
        self.total_pages = len(self.pages)
        self.is_paginated = self.total_pages > 1
        self.max_page_number = self.total_pages - 1

    def get_keyboard(
            self,
            page_number: int = 0,
            callback_data_prefix: str = '',
            page_callback_data_postfix: str = '',
            main_menu_button: InlineKeyboardButton = None
    ) -> list[list[InlineKeyboardButton]]:
        page_number = min(max(0, page_number), self.total_pages)
        keyboard = [
            [InlineKeyboardButton(
                item.button_text,
                callback_data=f'{callback_data_prefix}{item.callback_data}'
            )]
            for item in self.pages[page_number]
        ]

        keyboard_menu_buttons = [main_menu_button] if main_menu_button else []
        if self.max_page_number >= page_number > 0:
            keyboard_menu_buttons.insert(
                0,
                InlineKeyboardButton(
                    f'< стр. {page_number} из {self.total_pages}',
                    callback_data=f'page_{page_number - 1}{page_callback_data_postfix}'
                )
            )
        if page_number < self.max_page_number:
            keyboard_menu_buttons.append(
                InlineKeyboardButton(
                    f'стр. {page_number + 2} из {self.total_pages} >',
                    callback_data=f'page_{page_number + 1}{page_callback_data_postfix}'
                )
            )
        keyboard.append(keyboard_menu_buttons)
        return keyboard
