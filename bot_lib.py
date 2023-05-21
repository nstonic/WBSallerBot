from collections import Counter
from datetime import datetime
from functools import partial

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from stickers import get_supply_sticker, get_orders_stickers
from paginator import Paginator
from utils import convert_to_created_ago
from wb_api.classes import Order
from wb_api.client import WBApiClient
from wb_api.errors import WBAPIError
from redis_client import RedisClient

MAIN_MENU_BUTTON = InlineKeyboardButton('Основное меню', callback_data='start')


def show_start_menu(update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton('Показать поставки', callback_data='show_supplies')],
        [InlineKeyboardButton('Новые заказы', callback_data='new_orders')]
    ]
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=user_id,
        text='Основное меню',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_MAIN_MENU'


def show_supplies(
        update: Update, context:
        CallbackContext,
        quantity=50,
        page_number: int = 0,
        page_size: int = 10
):
    wb_api_client = WBApiClient()
    supplies = wb_api_client.get_supplies(only_active=False, quantity=quantity)
    paginator = Paginator(supplies, page_size)
    keyboard = paginator.get_keyboard(
        page_number=page_number,
        main_menu_button=MAIN_MENU_BUTTON,
        callback_data_prefix='supply_'
    )
    if paginator.is_paginated:
        text = 'Список поставок\n' \
               f'(стр. {page_number + 1})'
    else:
        text = 'Список поставок\n'

    keyboard.insert(
        -1,
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')]
    )
    if update.effective_message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_SUPPLIES_MENU'


def show_new_orders(
        update: Update,
        context: CallbackContext,
        page_number: int = 0,
        page_size: int = 10
):
    wb_api_client = WBApiClient()
    new_orders = wb_api_client.get_new_orders()
    if new_orders:
        paginator = Paginator(new_orders, page_size)
        keyboard = paginator.get_keyboard(
            page_number=page_number,
            main_menu_button=MAIN_MENU_BUTTON
        )
        if paginator.is_paginated:
            text = f'Новые заказы (стр. {page_number + 1}):\n' \
                   f'Всего {paginator.items_count}шт\n' \
                   f'(Артикул | Время с момента заказа)'
        else:
            text = 'Новые заказы:\n' \
                   f'Всего {paginator.items_count}шт\n' \
                   '(Артикул | Время с момента заказа)'
    else:
        text = 'Нет новых заказов'
        keyboard = [MAIN_MENU_BUTTON]

    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_NEW_ORDERS'


def show_supply(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    supply = wb_api_client.get_supply(supply_id)
    orders = wb_api_client.get_supply_orders(supply_id)
    if orders:
        keyboard = [
            [InlineKeyboardButton('Создать стикеры', callback_data=f'stickers_{supply_id}')]
        ]
        if not supply.is_done:
            keyboard.insert(
                1,
                [InlineKeyboardButton('Редактировать заказы', callback_data=f'edit_{supply_id}')]
            )
            keyboard.insert(
                1,
                [InlineKeyboardButton('Отправить в доставку', callback_data=f'close_{supply_id}')]
            )
        articles = [order.article for order in orders]
        joined_orders = '\n'.join(
            [f'{article} - {count}шт.'
             for article, count in Counter(sorted(articles)).items()]
        )
        text = f'Заказы по поставке {supply_id}:\n\n{joined_orders}'
    else:
        keyboard = [
            [InlineKeyboardButton('Удалить поставку', callback_data=f'delete_{supply_id}')]
        ]
        text = f'В поставке нет заказов'

    keyboard.extend([
        [InlineKeyboardButton('Назад к списку поставок', callback_data='show_supplies')],
        [MAIN_MENU_BUTTON]
    ])
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_SUPPLY'


def edit_supply(
        update: Update,
        context: CallbackContext,
        supply_id: str,
        page_number: int = 0,
        page_size: int = 10
):
    wb_api_client = WBApiClient()
    paginator = Paginator(
        item_list=wb_api_client.get_supply_orders(supply_id),
        page_size=page_size
    )
    keyboard = paginator.get_keyboard(
        page_number=page_number,
        main_menu_button=MAIN_MENU_BUTTON,
        callback_data_prefix=f'{supply_id}_'
    )
    keyboard.insert(
        -1,
        [InlineKeyboardButton(
            'Вернуться к поставке',
            callback_data=f'supply_{supply_id}'
        )]
    )
    if paginator.is_paginated:
        text = f'Заказы в поставке {supply_id} (стр. {page_number + 1}):\n' \
               f'Всего {paginator.items_count}шт\n' \
               f'(Артикул | Время с момента заказа)'
    else:
        text = f'Заказы в поставке {supply_id}:\n' \
               f'Всего {paginator.items_count}шт\n' \
               '(Артикул | Время с момента заказа)'

    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_EDIT_SUPPLY'


def send_message_with_order_details(
        update: Update,
        context: CallbackContext,
        order: Order,
        back_button: InlineKeyboardButton
):
    keyboard = [
        [InlineKeyboardButton('Перенести в поставку', callback_data=f'add_to_supply_{order.id}')],
        [back_button],
        [MAIN_MENU_BUTTON]
    ]
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Номер заказа: <b>{order.id}</b>\n'
             f'Артикул: <b>{order.article}</b>\n'
             f'Поставка: <b>{order.supply_id}</b>\n'
             f'Время с момента заказа: <b>{convert_to_created_ago(order.created_at)}</b>\n'
             f'Цена: <b>{order.converted_price / 100} ₽</b>\n',
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


def show_order_details(
        update: Update,
        context: CallbackContext,
        order_id: int,
        supply_id: str
):
    wb_api_client = WBApiClient()
    context.bot.answer_callback_query(
        update.callback_query.id,
        f'Загружает информация по заказу {order_id}'
    )
    orders = wb_api_client.get_supply_orders(supply_id)
    for order in orders:
        if order.id == order_id:
            current_order = order
            break
    else:
        return

    back_button = InlineKeyboardButton(
        'Вернуться к поставке',
        callback_data=f'supply_{supply_id}'
    )
    send_message_with_order_details(
        update,
        context,
        current_order,
        back_button
    )
    return 'HANDLE_ORDER_DETAILS'


def show_new_order_details(update: Update, context: CallbackContext, order_id: int):
    wb_api_client = WBApiClient()
    for order in wb_api_client.get_new_orders():
        if order.id == order_id:
            current_order = order
            break
    else:
        return

    context.bot.answer_callback_query(
        update.callback_query.id,
        f'Информация по заказу {current_order.id}'
    )
    back_button = InlineKeyboardButton(
        'Вернуться к списку заказов',
        callback_data=f'new_orders'
    )
    send_message_with_order_details(
        update,
        context,
        current_order,
        back_button
    )
    return 'HANDLE_ORDER_DETAILS'


def send_stickers(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    context.bot.answer_callback_query(
        update.callback_query.id,
        'Запущена подготовка стикеров. Подождите'
    )
    orders = wb_api_client.get_supply_orders(supply_id)
    order_qr_codes = wb_api_client.get_qr_codes_for_orders(
        [order.id for order in orders]
    )
    articles = set([order.article for order in orders])
    products = [wb_api_client.get_product(article) for article in articles]
    zip_file = get_orders_stickers(
        orders,
        products,
        order_qr_codes,
        supply_id
    )
    context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=zip_file.getvalue(),
        filename=zip_file.name
    )


def close_supply(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    status_code = wb_api_client.send_supply_to_deliver(supply_id)
    if status_code != 204:
        raise WBAPIError(message=update.callback_query.data, code=status_code)
    context.bot.answer_callback_query(update.callback_query.id, 'Отправлено в доставку')
    supply_sticker = get_supply_sticker(supply_id)
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=supply_sticker
    )
    return show_supplies(update, context)


def ask_to_choose_supply(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    active_supplies = wb_api_client.get_supplies()
    order_id = update.callback_query.data.replace('add_to_supply_', '')
    keyboard = []
    for supply in active_supplies:
        button_name = f'{supply.name} | {supply.id}'
        keyboard.append([
            InlineKeyboardButton(button_name, callback_data=f'{supply.id}_{order_id}')
        ])

    keyboard.extend([
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')],
        [MAIN_MENU_BUTTON]
    ])
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите поставку',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_SUPPLY_CHOICE'


def add_order_to_supply(update: Update, context: CallbackContext):
    supply_id, order_id = update.callback_query.data.split('_')
    wb_api_client = WBApiClient()
    wb_api_client.add_order_to_supply(supply_id, order_id)
    return show_supply(update, context, supply_id)


def ask_for_supply_name(update: Update, context: CallbackContext):
    redis = RedisClient()
    keyboard = [
        [InlineKeyboardButton('Назад к списку поставок', callback_data='cancel')],
        [MAIN_MENU_BUTTON]
    ]
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    message = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Напишите название для новой поставки',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    redis.client.set(f'message_{update.effective_chat.id}', message.message_id)
    return 'HANDLE_NEW_SUPPLY_NAME'


def create_new_supply(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    redis = RedisClient()
    new_supply_name = update.message.text
    wb_api_client.create_new_supply(new_supply_name)
    message_to_delete = redis.client.get(f'message_{update.effective_message.from_user.id}')
    if message_to_delete:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_to_delete.decode('utf-8')
        )
    update.message = None
    return show_supplies(update, context)


def delete_supply(update, context, supply_id: str):
    wb_api_client = WBApiClient()
    wb_api_client.delete_supply_by_id(supply_id)
    context.bot.answer_callback_query(
        update.callback_query.id,
        'Поставка удалена'
    )
    return show_supplies(update, context)
