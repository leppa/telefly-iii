import json
import logging
import os

from configparser import ConfigParser
from datetime import datetime

from firefly_iii_client import (
    AccountTypeFilter,
    AccountsApi,
    ApiClient,
    BudgetsApi,
    CategoriesApi,
    Transaction,
    TransactionSplit,
    TransactionsApi,
)
from firefly_iii_client.configuration import Configuration
from firefly_iii_client.rest import ApiException

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    PicklePersistence,
    Updater,
)
from telegram.utils.helpers import escape_markdown

logger = logging.getLogger(__name__)

FIREFLY_URL, FIREFLY_TOKEN, SOURCE_ACCOUNT = range(3)
EXPENSE_ACCOUNT, CATEGORY, BUDGET = range(3)


def configure_callback(update, context):
    del context  # unused

    update.message.reply_text(
        """Hi! Let's configure your bot.

What is your Firefly III URL?"""
    )
    return FIREFLY_URL


def firefly_url_callback(update, context):
    context.user_data["firefly_url"] = update.message.text
    request_firefly_token(update, context)
    return FIREFLY_TOKEN


def request_firefly_token(update, context):
    update.message.reply_markdown(
        "What is your [Personal Access Token]({}/profile)?".format(
            context.user_data["firefly_url"]
        )
    )


def firefly_token_callback(update, context):
    context.user_data["firefly_token"] = update.message.text
    request_source_account(update, context)
    return SOURCE_ACCOUNT


def request_source_account(update, context):
    reply_markup = get_account_list(context, AccountTypeFilter.ASSET)
    message = update.message.reply_text(
        "From which account do you want to spend?", reply_markup=reply_markup
    )
    context.user_data["last_inline_message_id"] = message.message_id


def source_account_callback(update, context):
    query = update.callback_query
    if not query:
        context.bot.edit_message_reply_markup(
            chat_id=update.message.chat.id,
            message_id=context.user_data["last_inline_message_id"],
        )
        request_source_account(update, context)
        return SOURCE_ACCOUNT

    context.user_data["last_inline_message_id"] = None
    context.user_data["firefly_spending_account"] = query.data
    query.edit_message_text(
        """All set! Simply type your expense and a description. E.g., `10 Coffee with\
 friends`. Or use /help to get more details.""",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


def get_account_list(context, account_type=AccountTypeFilter.EXPENSE):
    api = AccountsApi(get_api_client(context))
    accounts = api.list_account(type=account_type).data
    accounts_keyboard = [[]]
    for account in accounts:
        account_name = account.attributes.name
        if len(accounts_keyboard[-1]) < 3:
            accounts_keyboard[-1].append(
                InlineKeyboardButton(account_name, callback_data=account.id)
            )
        else:
            accounts_keyboard.append(
                [InlineKeyboardButton(account_name, callback_data=account.id)]
            )

    return InlineKeyboardMarkup(accounts_keyboard)


def get_category_list(context):
    api = CategoriesApi(get_api_client(context))
    categories = api.list_category().data
    categories_keyboard = [[]]
    for category in categories:
        category_name = category.attributes.name
        if len(categories_keyboard[-1]) < 3:
            categories_keyboard[-1].append(
                InlineKeyboardButton(category_name, callback_data=category.id)
            )
        else:
            categories_keyboard.append(
                [InlineKeyboardButton(category_name, callback_data=category.id)]
            )
    categories_keyboard.append([InlineKeyboardButton("(none)", callback_data=0)])

    return InlineKeyboardMarkup(categories_keyboard)


def get_budget_list(context):
    api = BudgetsApi(get_api_client(context))
    budgets = api.list_budget().data
    budgets_keyboard = [[]]
    for budget in budgets:
        budget_name = budget.attributes.name
        if len(budgets_keyboard[-1]) < 3:
            budgets_keyboard[-1].append(
                InlineKeyboardButton(budget_name, callback_data=budget.id)
            )
        else:
            budgets_keyboard.append(
                [InlineKeyboardButton(budget_name, callback_data=budget.id)]
            )
    budgets_keyboard.append([InlineKeyboardButton("(none)", callback_data=0)])

    return InlineKeyboardMarkup(budgets_keyboard)


def start_transaction_callback(update, context):
    message = update.message.text.split(" ", 1)
    if not context.user_data.get("firefly_spending_account") or len(message) < 2:
        help_callback(update, context)
        return ConversationHandler.END

    context.user_data["transaction"] = {
        "type": "withdrawal",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": message[0].replace(",", "."),
        "description": message[1],
        "source_id": context.user_data.get("firefly_spending_account"),
    }

    request_expense_account(update, context)
    return EXPENSE_ACCOUNT


def request_expense_account(update, context):
    prompt = """Where or to whom did you pay the money (*Expense account*)?
You can also type your answer."""
    reply_markup = get_account_list(context)
    message = update.message.reply_markdown(prompt, reply_markup=reply_markup)
    context.user_data["last_inline_message_id"] = message.message_id


def expense_account_callback(update, context):
    query = update.callback_query
    if query is not None:
        context.user_data["transaction"]["destination_id"] = query.data
    else:
        context.user_data["transaction"]["destination_name"] = update.message.text

    request_category(update, context)
    return CATEGORY


def request_category(update, context):
    prompt = """Which *category* does it fall in?
You can also type your answer."""
    reply_markup = get_category_list(context)
    query = update.callback_query
    if query:
        query.edit_message_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )
    else:
        context.bot.edit_message_reply_markup(
            chat_id=update.message.chat.id,
            message_id=context.user_data["last_inline_message_id"],
        )
        message = update.message.reply_markdown(prompt, reply_markup=reply_markup)
        context.user_data["last_inline_message_id"] = message.message_id


def category_callback(update, context):
    query = update.callback_query
    if query:
        if int(query.data) > 0:
            context.user_data["transaction"]["category_id"] = query.data
    else:
        context.user_data["transaction"]["category_name"] = update.message.text

    request_budget(update, context)
    return BUDGET


def request_budget(update, context):
    prompt = """Is there a *budget* for this?
Please, select from the list."""
    reply_markup = get_budget_list(context)
    query = update.callback_query
    if query:
        query.edit_message_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )
    else:
        context.bot.edit_message_reply_markup(
            chat_id=update.message.chat.id,
            message_id=context.user_data["last_inline_message_id"],
        )
        message = update.message.reply_markdown(prompt, reply_markup=reply_markup)
        context.user_data["last_inline_message_id"] = message.message_id


def budget_callback(update, context):
    query = update.callback_query
    if not query:
        request_budget(update, context)
        return BUDGET

    if int(query.data) > 0:
        context.user_data["transaction"]["budget_id"] = query.data

    context.user_data["last_inline_message_id"] = None
    store_transaction(update, context)
    return ConversationHandler.END


def store_transaction(update, context):
    query = update.callback_query
    api = TransactionsApi(get_api_client(context))
    transaction = Transaction(
        transactions=[TransactionSplit(**context.user_data["transaction"])]
    )
    try:
        ts = api.store_transaction(transaction).data.attributes.transactions[0]
        message = """The following transaction was created successfully:
_{source}_ -> *{currency}-{amount}* -> _{destination}_
Description: _{description}_
Category: _{category}_
Budget: _{budget}_"""
        query.edit_message_text(
            message.format(
                amount=round(float(ts.amount), ts.currency_decimal_places),
                currency=ts.currency_symbol,
                description=escape_markdown(ts.description),
                source=escape_markdown(ts.source_name),
                destination=escape_markdown(ts.destination_name),
                category=escape_markdown(ts.category_name or "(none)"),
                budget=escape_markdown(ts.budget_name or "(none)"),
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except ApiException as e:
        reason = e.reason
        if e.body:
            reason = json.loads(e.body).get("message")
        query.edit_message_text(
            "Failed to create a transaction: *{}*".format(reason),
            parse_mode=ParseMode.MARKDOWN,
        )


def about_callback(update, context):
    del context  # unused

    update.message.reply_markdown(
        """*Telefly III - A Telegram bot for Firefly III*

This is a Telegram bot for [Firefly III](https://www.firefly-iii.org/), which you can\
 use to submit your expenses on the go. You start entering a new transaction by\
 sending an amount and a description (e.g., `5 Coffee with friends`). Afterwards,\
 *Telefly III* will ask you about the destination account, category, and budget. These\
 will be fetched from your Firefly III installation and presented as a list of\
 buttons. In case of destination account and category, you can either select an option\
 from the list, or you can type your answer directly. If there's no such account or\
 category, it will be created automatically. As for the budget, you can only select\
 the one from the list. There's also an option not to specify category or budget by\
 selecting *(none)*.

Homepage: https://github.com/leppa/telefly-iii"""
    )


def get_api_client(context):
    config = Configuration()
    config.host = context.user_data.get("firefly_url")
    config.access_token = context.user_data.get("firefly_token")
    return ApiClient(config)


def help_callback(update, context):
    if not context.user_data.get("firefly_spending_account"):
        update.message.reply_text(
            "The bot is not fully configured. "
            "Use /configure to initiate the configuration process."
        )
    else:
        update.message.reply_markdown(
            """Just type in your an expense with a description, to start creating a\
 transaction. E.g., `5 Coffee with friends`.

Afterwards, you will be asked to provide destination account, category and budget. You\
 can select from the presented list or, in case of destination account and category,\
 type in your answer. If there is no account or category with typed in name, it will\
 be created automatically.

You can cancel the creation of transaction at any time, by simply sending /cancel.

Use /configure to change your Firefly III URL, personal access token, and account."""
        )


def cancel(update, context):
    if context.user_data["last_inline_message_id"]:
        context.bot.edit_message_reply_markup(
            chat_id=update.message.chat.id,
            message_id=context.user_data["last_inline_message_id"],
        )
        context.user_data["last_inline_message_id"] = None
    update.message.reply_text("Cancelled")

    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    config_file = os.getenv("TELEFLY_III_CONFIG")
    if not config_file:
        config_file = os.path.join("config", "telefly-iii.ini")
    config = ConfigParser()
    # Defaults
    config.read_dict({"Persistence": {"path": "config", "filename_prefix": "telefly"}})
    config.read(config_file)

    data_dir = os.path.expanduser(config["Persistence"]["path"])
    os.makedirs(data_dir, exist_ok=True)
    filename_prefix = config["Persistence"]["filename_prefix"]
    bot_persistence = PicklePersistence(
        filename=os.path.join(data_dir, filename_prefix), single_file=False
    )
    bot_token = config["Bot"]["token"]
    if not bot_token:
        logger.critical("Please, provide Telegram bot token in the config file.")
        return 1

    updater = Updater(bot_token, persistence=bot_persistence, use_context=True)

    text_without_command = Filters.text & (~Filters.command)
    conversation_handler_setup = ConversationHandler(
        entry_points=[
            CommandHandler("start", configure_callback),
            CommandHandler("configure", configure_callback),
        ],
        states={
            FIREFLY_URL: [MessageHandler(text_without_command, firefly_url_callback)],
            FIREFLY_TOKEN: [
                MessageHandler(text_without_command, firefly_token_callback)
            ],
            SOURCE_ACCOUNT: [
                CallbackQueryHandler(source_account_callback),
                MessageHandler(text_without_command, source_account_callback),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conversation_handler_spend = ConversationHandler(
        entry_points=[
            MessageHandler(
                Filters.regex("^[0-9]+([\\.,][0-9]+)? .+"), start_transaction_callback
            )
        ],
        states={
            EXPENSE_ACCOUNT: [
                CallbackQueryHandler(expense_account_callback),
                MessageHandler(text_without_command, expense_account_callback),
            ],
            CATEGORY: [
                CallbackQueryHandler(category_callback),
                MessageHandler(text_without_command, category_callback),
            ],
            BUDGET: [
                CallbackQueryHandler(budget_callback),
                MessageHandler(text_without_command, budget_callback),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    updater.dispatcher.add_handler(conversation_handler_setup)
    updater.dispatcher.add_handler(conversation_handler_spend)
    updater.dispatcher.add_handler(CommandHandler("help", help_callback))
    updater.dispatcher.add_handler(CommandHandler("about", about_callback))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, help_callback))
    updater.dispatcher.add_error_handler(error)

    updater.start_polling()

    updater.idle()

    return 0
