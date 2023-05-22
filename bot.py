import logging
from functools import partial

from environs import Env
from telegram import Update
from telegram.ext import (
    Updater,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    Filters,
    CallbackContext
)

from wb_api.client import WBApiClient
from bot_lib import (
    show_start_menu,
    show_supplies,
    show_new_orders,
    show_supply,
    show_new_order_details,
    send_stickers,
    close_supply,
    ask_to_choose_supply,
    add_order_to_supply,
    ask_for_supply_name,
    create_new_supply,
    delete_supply,
    edit_supply,
    show_order_details, get_confirmation_to_close_supply
)
from logger import TGLoggerHandler
from redis_client import RedisClient

tg_logger = logging.getLogger('TG_logger')


def handle_main_menu(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query == 'show_supplies':
        return show_supplies(update, context)
    if query == 'new_orders':
        return show_new_orders(update, context)


def handle_supplies_menu(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('supply_'):
        _, supply_id = query.split('_', maxsplit=1)
        return show_supply(update, context, supply_id)
    if query == 'new_supply':
        return ask_for_supply_name(update, context)
    if query.startswith('page_'):
        _, page_number = query.split('_', maxsplit=2)
        return show_supplies(update, context, page_number=int(page_number))


def handle_supply(update: Update, context: CallbackContext):
    query = update.callback_query.data
    _, supply_id = query.split('_', maxsplit=1)
    if query.startswith('stickers_'):
        return send_stickers(update, context, supply_id)
    if query.startswith('close_'):
        return get_confirmation_to_close_supply(update, context, supply_id)
    if query.startswith('delete_'):
        return delete_supply(update, context, supply_id)
    if query.startswith('edit_'):
        return edit_supply(update, context, supply_id)
    if query.startswith('show_supplies'):
        return show_supplies(update, context)


def handle_confirmation_to_close_supply(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('yes_'):
        supply_id = query.replace('yes_', '')
        return close_supply(update, context, supply_id)
    if query == 'no':
        return show_supplies(update, context)


def handle_order_details(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('add_to_supply_'):
        return ask_to_choose_supply(update, context)
    if query.startswith('supply_'):
        _, supply_id = query.split('_', maxsplit=1)
        return show_supply(update, context, supply_id)
    if query == 'new_orders':
        return show_new_orders(update, context)


def handle_new_supply_name(update: Update, context: CallbackContext):
    if update.message:
        return create_new_supply(update, context)
    if update.callback_query.data == 'cancel':
        return show_supplies(update, context)


def handle_new_orders(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('page_'):
        _, page = query.split('_', maxsplit=1)
        return show_new_orders(update, context, int(page))
    else:
        order_id = int(update.callback_query.data)
        return show_new_order_details(update, context, order_id)


def handle_supply_choice(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query == 'new_supply':
        return ask_for_supply_name(update, context)
    else:
        return add_order_to_supply(update, context)


def handle_edit_supply(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query.startswith('page_'):
        page_callback_data, supply_callback_data = query.split(' ', maxsplit=1)
        page = page_callback_data.replace('page_', '')
        supply_id = supply_callback_data.replace('supply_', '')
        return edit_supply(update, context, supply_id=supply_id, page_number=int(page))
    elif query.startswith('supply_'):
        _, supply_id = query.split('_', maxsplit=1)
        return show_supply(update, context, supply_id)
    else:
        supply_id, order_id = query.split('_', maxsplit=1)
        return show_order_details(update, context, int(order_id), supply_id)


def handle_users_reply(update: Update, context: CallbackContext, user_ids: int):
    db = RedisClient()

    if update.effective_chat.id not in user_ids:
        return

    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
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

    if user_state not in ['HANDLE_NEW_SUPPLY_NAME', 'START']:
        if update.message:
            context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            return

    state_functions = {
        'START': show_start_menu,
        'HANDLE_MAIN_MENU': handle_main_menu,
        'HANDLE_SUPPLIES_MENU': handle_supplies_menu,
        'HANDLE_NEW_ORDERS': handle_new_orders,
        'HANDLE_SUPPLY': handle_supply,
        'HANDLE_ORDER_DETAILS': handle_order_details,
        'HANDLE_NEW_SUPPLY_NAME': handle_new_supply_name,
        'HANDLE_SUPPLY_CHOICE': handle_supply_choice,
        'HANDLE_EDIT_SUPPLY': handle_edit_supply,
        'HANDLE_CONFIRMATION_TO_CLOSE_SUPPLY': handle_confirmation_to_close_supply
    }

    state_handler = state_functions.get(user_state, show_start_menu)
    next_state = state_handler(
        update=update,
        context=context
    ) or user_state
    db.client.set(chat_id, next_state)


def error_handler(update: Update, context: CallbackContext):
    tg_logger.error(msg='Ошибка в боте', exc_info=context.error)


def main():
    env = Env()
    env.read_env()
    WBApiClient(token=env('WB_API_KEY'))
    RedisClient(
        host=env('REDIS_URL'),
        port=env('REDIS_PORT'),
        password=env('REDIS_PASSWORD')
    )
    handle_users_reply_with_owner_id = partial(
        handle_users_reply,
        user_ids=env.list('USER_IDS', subcast=int)
    )
    token = env('TG_TOKEN')
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply_with_owner_id))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply_with_owner_id))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply_with_owner_id))
    if tg_token := env('TG_LOGGER_TOKEN', None):
        tg_logger.setLevel(logging.WARNING)
        tg_logger.addHandler(TGLoggerHandler(
            tg_token=tg_token,
            chat_id=env.int('ADMIN_ID')
        ))
        dispatcher.add_error_handler(error_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
