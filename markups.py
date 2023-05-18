from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from api.classes import Supply


def create_supplies_markup(
        supplies: list[Supply],
        show_more_supplies: bool = True,
        show_create_new: bool = False
) -> InlineKeyboardMarkup:

    is_done = {0: 'Открыта', 1: 'Закрыта'}
    keyboard = []
    for supply in supplies:
        button_name = f'{supply.name} | {supply.supply_id} | {is_done[supply.is_done]}'
        keyboard.append([InlineKeyboardButton(button_name, callback_data=f'supply_{supply.supply_id}')])

    if show_more_supplies:
        keyboard.append(
            InlineKeyboardButton(
                text='Показать больше поставок',
                callback_data=f'more_supplies'
            )
        )
    if show_create_new:
        keyboard.append(
            InlineKeyboardButton(
                text='Создать новую',
                callback_data=f'create_supply'
            )
        )
    return InlineKeyboardMarkup(keyboard)
