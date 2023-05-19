from base64 import b64decode
from collections import Counter
from datetime import datetime
from io import BytesIO

import pytz
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CallbackContext

from api.client import WBApiClient
from api.errors import WBAPIError
from config import TIME_ZONE
from redis_client import RedisClient


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


def show_supplies(update: Update, context: CallbackContext, only_active=True, limit=10):
    wb_api_client = WBApiClient()
    active_supplies = wb_api_client.get_supplies(only_active, limit)

    is_done = {0: 'Открыта', 1: 'Закрыта'}
    keyboard = []
    for supply in active_supplies:
        button_name = f'{supply.name} | {supply.supply_id} | {is_done[supply.is_done]}'
        keyboard.append([
            InlineKeyboardButton(button_name, callback_data=f'supply_{supply.supply_id}')
        ])
    keyboard.extend([
        [InlineKeyboardButton('Показать больше поставок', callback_data='more_supplies')],
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')],
        [InlineKeyboardButton('Основное меню', callback_data='start')]
    ])
    if update.effective_message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Текущие незакрытые поставки',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_SUPPLIES_MENU'


def show_new_orders(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    new_orders = wb_api_client.get_new_orders()
    keyboard = [
        [InlineKeyboardButton(
            f'{order.article} | {convert_to_created_ago(order.created_at)}',
            callback_data=order.order_id
        )]
        for order in new_orders
    ]
    keyboard.append(
        [InlineKeyboardButton('Основное меню', callback_data='start')]
    )
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Новые заказы:\n(Артикул | Время с момента заказа)',
        reply_markup=InlineKeyboardMarkup(keyboard)

    )
    return 'HANDLE_NEW_ORDERS'


def show_supply(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    orders = wb_api_client.get_supply_orders(supply_id)
    if orders:
        keyboard = [
            [InlineKeyboardButton('Создать стикеры', callback_data=f'stickers_{supply_id}')],
            [InlineKeyboardButton('Отправить в доставку', callback_data=f'close_{supply_id}')],
            [InlineKeyboardButton('Основное меню', callback_data='start')]
        ]
        articles = [order.article for order in orders]
        joined_orders = '\n'.join(
            [f'{article} - {count}шт.'
             for article, count in Counter(sorted(articles)).items()]
        )
        text = f'Заказы по поставке {supply_id}:\n\n{joined_orders}'
    else:
        keyboard = [
            [InlineKeyboardButton('Удалить поставку', callback_data=f'delete_{supply_id}')],
            [InlineKeyboardButton('Отправить в доставку', callback_data=f'close_{supply_id}')],  # DELETE_ME
            [InlineKeyboardButton('Основное меню', callback_data='start')]
        ]
        text = f'В поставке нет заказов'

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


def show_order_details(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    for order in wb_api_client.get_new_orders():
        if order.order_id == int(update.callback_query.data):
            current_order = order
            break
    else:
        return

    context.bot.answer_callback_query(
        update.callback_query.id,
        f'Информация по заказу {current_order.order_id}'
    )
    keyboard = [
        [InlineKeyboardButton('Перенести в поставку', callback_data=f'add_to_supply_{current_order.order_id}')],
        [InlineKeyboardButton('Вернуться к списку заказов', callback_data=f'new_orders')],
        [InlineKeyboardButton('Основное меню', callback_data='start')]
    ]
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Номер заказа: {current_order.order_id}\n'
             f'Артикул: {current_order.article}\n'
             f'Время с момента заказа: {convert_to_created_ago(order.created_at)}',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return 'HANDLE_ORDER'


def send_stickers(update: Update, context: CallbackContext, supply_id: str):
    pass


def close_supply(update: Update, context: CallbackContext, supply_id: str):
    wb_api_client = WBApiClient()
    status_code = wb_api_client.send_supply_to_deliver(supply_id)
    if status_code != 204:
        raise WBAPIError(message=update.callback_query.data, code=status_code)
    context.bot.answer_callback_query(update.callback_query.id, 'Отправлено в доставку')

    supply_sticker = wb_api_client.get_supply_sticker(supply_id)
    sticker_in_byte_format = b64decode(supply_sticker.image_string, validate=True)
    image = Image.open(
        BytesIO(
            sticker_in_byte_format
        )
    ).rotate(-90, expand=True)
    image_to_sending = BytesIO()
    image.save(image_to_sending, format='PNG')

    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image_to_sending.getvalue()
    )
    return show_supplies(update, context)


def ask_for_supply_id(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    active_supplies = wb_api_client.get_supplies()
    _, order_id = update.callback_query.data.split('_', maxsplit=1)
    keyboard = []
    for supply in active_supplies:
        button_name = f'{supply.name} | {supply.supply_id}'
        keyboard.append([
            InlineKeyboardButton(button_name, callback_data=f'{supply.supply_id}_{order_id}')
        ])

    keyboard.extend([
        [InlineKeyboardButton('Создать новую поставку', callback_data='new_supply')],
        [InlineKeyboardButton('Назад к списку заказов', callback_data='new_orders')],
        [InlineKeyboardButton('Основное меню', callback_data='start')]
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
        [InlineKeyboardButton('Основное меню', callback_data='start')]
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
    message_to_delete = redis.client.get(f'message_{update.effective_message.from_user.id}').decode('utf-8')
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


def convert_to_created_ago(created_at: datetime) -> str:
    created_ago = datetime.now().astimezone(pytz.timezone(TIME_ZONE)) - \
                  created_at.astimezone(pytz.timezone(TIME_ZONE))
    hours, seconds = divmod(created_ago.seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}'
