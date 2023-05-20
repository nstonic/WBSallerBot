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
    show_order_details,
    send_stickers,
    close_supply,
    ask_for_supply_id,
    add_order_to_supply,
    ask_for_supply_name,
    create_new_supply,
    delete_supply
)
from logger import TGLoggerHandler
from redis_client import RedisClient

tg_logger = logging.getLogger('TG_logger')


def handle_main_menu(update: Update, context: CallbackContext):
    if update.message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        return
    query = update.callback_query.data
    if query == 'show_supplies':
        return show_supplies(update, context)
    if query == 'new_orders':
        return show_new_orders(update, context)


def handle_supplies_menu(update: Update, context: CallbackContext):
    if update.message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        return
    query = update.callback_query.data
    if query.startswith('supply_'):
        _, supply_id = query.split('_', maxsplit=1)
        return show_supply(update, context, supply_id)
    if query == 'more_supplies':
        return show_supplies(update, context, only_active=False)
    if query == 'new_supply':
        return ask_for_supply_name(update, context)


def handle_supply(update: Update, context: CallbackContext):
    if update.message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        return
    query = update.callback_query.data
    _, supply_id = query.split('_', maxsplit=1)
    if query.startswith('stickers_'):
        return send_stickers(update, context, supply_id)
    if query.startswith('close_'):
        return close_supply(update, context, supply_id)
    if query.startswith('delete_'):
        return delete_supply(update, context, supply_id)


def handle_order(update: Update, context: CallbackContext):
    if update.message:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        return
    query = update.callback_query.data
    if query.startswith('add_'):
        return ask_for_supply_id(update, context)
    if query == 'new_orders':
        return show_new_orders(update, context)


def handle_new_supply_name(update: Update, context: CallbackContext):
    if update.message:
        return create_new_supply(update, context)
    if update.callback_query.data == 'cancel':
        return show_supplies(update, context)


def handle_supply_choice(update: Update, context: CallbackContext):
    query = update.callback_query.data
    if query == 'new_orders':
        return show_new_orders(update, context)
    if query == 'new_supply':
        return ask_for_supply_name(update, context)
    if query == 'add_':
        return add_order_to_supply(update, context)


def handle_users_reply(update: Update, context: CallbackContext, owner_id: int):
    db = RedisClient()

    if not update.effective_chat.id == owner_id:
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
    state_functions = {
        'START': show_start_menu,
        'HANDLE_MAIN_MENU': handle_main_menu,
        'HANDLE_SUPPLIES_MENU': handle_supplies_menu,
        'HANDLE_NEW_ORDERS': show_order_details,
        'HANDLE_SUPPLY': handle_supply,
        'HANDLE_ORDER': handle_order,
        'HANDLE_NEW_SUPPLY_NAME': handle_new_supply_name,
        'HANDLE_SUPPLY_CHOICE': handle_supply_choice
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
    handle_users_reply_with_owner_id = partial(handle_users_reply, owner_id=env.int('OWNER_ID'))
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
