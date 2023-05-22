from collections import Counter

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from stickers import get_supply_sticker, get_orders_stickers
from paginator import Paginator
from utils import convert_to_created_ago
from wb_api.client import WBApiClient
from redis_client import RedisClient

_MAIN_MENU_BUTTON = InlineKeyboardButton('Основное меню', callback_data='start')


def answer_to_user(
        update: Update,
        context: CallbackContext,
        text: str,
        keyboard: list[list[InlineKeyboardButton]],
        add_main_menu_button: bool = True,
        parse_mode: str = 'HTML'
):
    if add_main_menu_button:
        keyboard.append([_MAIN_MENU_BUTTON])
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    return context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=parse_mode
    )


def show_start_menu(update: Update, context: CallbackContext):
    text = 'Основное меню'
    keyboard = [
        [InlineKeyboardButton('Показать поставки', callback_data='show_supplies')],
        [InlineKeyboardButton('Новые заказы', callback_data='new_orders')]
    ]
    answer_to_user(
        update,
        context,
        text,
        keyboard,
        add_main_menu_button=False
    )
    return 'HANDLE_MAIN_MENU'


def show_supplies(
        update: Update,
        context: CallbackContext,
        quantity: int = 50,
        page_number: int = 0,
        page_size: int = 10
):
    wb_api_client = WBApiClient()
    supplies = wb_api_client.get_supplies(only_active=False, quantity=quantity)
    sorted_orders = sorted(supplies, key=lambda s: s.created_at, reverse=True)
    paginator = Paginator(sorted_orders, page_size)
    keyboard = paginator.get_keyboard(
        page_number=page_number,
        callback_data_prefix='supply_',
        main_menu_button=_MAIN_MENU_BUTTON
    )
    text = 'Список поставок'
    if paginator.is_paginated:
        text = f'{text}\n(стр. {page_number + 1})'
    keyboard.insert(
        -1,
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')]
    )
    answer_to_user(
        update,
        context,
        text,
        keyboard,
        add_main_menu_button=False
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
    sorted_orders = sorted(new_orders, key=lambda o: o.created_at)
    paginator = Paginator(sorted_orders, page_size)
    keyboard = paginator.get_keyboard(
        page_number=page_number,
        main_menu_button=_MAIN_MENU_BUTTON,
    )
    if new_orders:
        page_info = f' (стр. {page_number + 1})' if paginator.is_paginated else ''
        text = f'Новые заказы{page_info}:\n' \
               f'Всего {paginator.items_count}шт\n' \
               f'(Артикул | Время с момента заказа)'
    else:
        text = 'Нет новых заказов'
    answer_to_user(
        update,
        context,
        text,
        keyboard,
        add_main_menu_button=False
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

    keyboard.append(
        [InlineKeyboardButton('Назад к списку поставок', callback_data='show_supplies')]
    )
    answer_to_user(
        update,
        context,
        text,
        keyboard
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
    orders = wb_api_client.get_supply_orders(supply_id)
    sorted_orders = sorted(orders, key=lambda o: o.created_at)
    paginator = Paginator(
        item_list=sorted_orders,
        page_size=page_size
    )
    keyboard = paginator.get_keyboard(
        page_number=page_number,
        callback_data_prefix=f'{supply_id}_',
        page_callback_data_postfix=f' supply_{supply_id}',
        main_menu_button=_MAIN_MENU_BUTTON
    )
    keyboard.insert(
        -1,
        [InlineKeyboardButton(
            'Вернуться к поставке',
            callback_data=f'supply_{supply_id}'
        )]
    )
    page_info = f' (стр. {page_number + 1})' if paginator.is_paginated else ''
    text = f'Заказы в поставке {supply_id}{page_info}:\n' \
           f'Всего {paginator.items_count}шт\n' \
           f'(Артикул | Время с момента заказа)'

    answer_to_user(
        update,
        context,
        text,
        keyboard,
        add_main_menu_button=False
    )
    return 'HANDLE_EDIT_SUPPLY'


def show_order_details(
        update: Update,
        context: CallbackContext,
        order_id: int,
        supply_id: str
):
    wb_api_client = WBApiClient()
    context.bot.answer_callback_query(
        update.callback_query.id,
        f'Информация по заказу {order_id}'
    )
    orders = wb_api_client.get_supply_orders(supply_id)
    for order in orders:
        if order.id == order_id:
            current_order = order
            break
    else:
        return

    order_qr_code, *_ = wb_api_client.get_qr_codes_for_orders([current_order.id])

    keyboard = [
        [InlineKeyboardButton('Перенести в поставку', callback_data=f'add_to_supply_{order.id}')],
        [InlineKeyboardButton('Вернуться к поставке', callback_data=f'supply_{supply_id}')]
    ]

    text = f'Номер заказа: <b>{current_order.id}</b>\n' \
           f'Стикер: <b>{order_qr_code.part_a} {order_qr_code.part_b}</b>\n' \
           f'Артикул: <b>{current_order.article}</b>\n' \
           f'Поставка: <b>{supply_id}</b>\n' \
           f'Время с момента заказа: <b>{convert_to_created_ago(current_order.created_at)}</b>\n' \
           f'Цена: <b>{current_order.converted_price / 100} ₽</b>'

    answer_to_user(
        update,
        context,
        text,
        keyboard
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
    keyboard = [
        [InlineKeyboardButton('Перенести в поставку', callback_data=f'add_to_supply_{order.id}')],
        [InlineKeyboardButton('Вернуться к списку заказов', callback_data=f'new_orders')]
    ]

    text = f'Номер заказа: <b>{current_order.id}</b>\n' \
           f'Артикул: <b>{current_order.article}</b>\n' \
           f'Время с момента заказа: <b>{convert_to_created_ago(current_order.created_at)}</b>\n' \
           f'Цена: <b>{current_order.converted_price / 100} ₽</b>'

    answer_to_user(
        update,
        context,
        text,
        keyboard
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

    keyboard.append(
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')]
    )
    text = 'Выберите поставку'
    answer_to_user(
        update,
        context,
        text,
        keyboard
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
        [InlineKeyboardButton('Назад к списку поставок', callback_data='cancel')]
    ]
    text = 'Пришлите мне название для новой поставки'
    message = answer_to_user(
        update,
        context,
        text,
        keyboard
    )
    redis.client.set(f'message_{update.effective_chat.id}', message.message_id)
    return 'HANDLE_NEW_SUPPLY_NAME'


def create_new_supply(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    redis = RedisClient()
    new_supply_name = update.message.text
    wb_api_client.create_new_supply(new_supply_name)
    message_to_delete = redis.client.get(
        f'message_{update.effective_message.from_user.id}'
    ).decode('utf-8')
    if message_to_delete:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_to_delete
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


def close_supply(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    wb_api_client.send_supply_to_deliver(supply_id)
    context.bot.answer_callback_query(
        update.callback_query.id,
        'Отправлено в доставку'
    )
    supply_sticker = get_supply_sticker(supply_id)
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=supply_sticker
    )
    return show_supplies(update, context)
