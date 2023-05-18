import logging
from collections import Counter

from environs import Env
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    Filters,
    CallbackContext
)

from logger import TGLoggerHandler
from redis_client import RedisClient
from api.client import WBApiClient
from utils import convert_to_created_ago

tg_logger = logging.getLogger('TG_logger')


def show_start_menu(update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton('Показать поставки', callback_data='show_supplies')],
        [InlineKeyboardButton('Новые заказы', callback_data='new_orders')]
    ]
    keyboard_markup = InlineKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    context.bot.send_message(
        chat_id=user_id,
        text='Основное меню',
        reply_markup=keyboard_markup
    )
    return 'HANDLE_MAIN_MENU'


def show_supplies(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    active_supplies = wb_api_client.get_supplies()

    is_done = {0: 'Открыта', 1: 'Закрыта'}
    keyboard = []
    for supply in active_supplies:
        button_name = f'{supply.name} | {supply.supply_id} | {is_done[supply.is_done]}'
        keyboard.append([
            InlineKeyboardButton(button_name, callback_data=f'supply_{supply.supply_id}')
        ])
    keyboard.extend([
        [InlineKeyboardButton('Показать больше поставок', callback_data='more_supplies')],
        [InlineKeyboardButton('Основное меню', callback_data='start')]
    ])
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


def show_supply(update: Update, context: CallbackContext):
    wb_api_client = WBApiClient()
    _, supply_id = update.callback_query.data.split('_')
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
            [InlineKeyboardButton('Удалить поставку', callback_data=f'delete_{supply_id}')]
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
        [InlineKeyboardButton('Перенести в поставку', callback_data=f'move_to_supply_{current_order.order_id}')],
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


def handle_main_menu(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query == 'show_supplies':
        return show_supplies(update, context)
    elif query == 'new_orders':
        return show_new_orders(update, context)


def handle_supplies_menu(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('supply_'):
        return show_supply(update, context)
    elif query == 'more_supplies':
        return


def handle_supply(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('stickers_'):
        return
    elif query.startswith('close_'):
        return


def handle_order(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('move_to_supply_'):
        return
    elif query == 'new_orders':
        return show_new_orders(update, context)


def handle_users_reply(update, context):
    db = RedisClient()

    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
        if not user_reply == '/start':
            context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.effective_message.message_id
            )
            return
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply in ['/start', 'start']:
        user_state = 'START'
        db.client.set(chat_id, user_state)
    else:
        user_state = db.client.get(chat_id).decode('utf-8')
    states_functions = {
        'START': show_start_menu,
        'HANDLE_MAIN_MENU': handle_main_menu,
        'HANDLE_SUPPLIES_MENU': handle_supplies_menu,
        'HANDLE_NEW_ORDERS': show_order_details,
        'HANDLE_SUPPLY': handle_supply,
        'HANDLE_ORDER': handle_order
    }

    state_handler = states_functions.get(user_state, show_start_menu)
    next_state = state_handler(
        update=update,
        context=context
    ) or user_state
    db.client.set(chat_id, next_state)


def error_handler(update: Update, context: CallbackContext):
    tg_logger.error(msg="шибка в боте", exc_info=context.error)


def main():
    env = Env()
    env.read_env()
    WBApiClient(token=env('WB_API_KEY'))
    RedisClient(
        password=env('REDIS_PASSWORD'),
        host=env('REDIS_URL'),
        port=env('REDIS_PORT')
    )
    tg_logger.setLevel(logging.WARNING)
    tg_logger.addHandler(TGLoggerHandler(
        tg_token=env('TG_TOKEN'),
        chat_id=env('OWNER_ID'),
    ))
    token = env('TG_TOKEN')
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    # dispatcher.add_error_handler(error_handler)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
