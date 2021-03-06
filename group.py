import asyncio
import logging
import os.path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ContentType, ChatType, ParseMode

from aiogram_dialog import Dialog, DialogManager, DialogRegistry, Window, ChatEvent, StartMode
from aiogram_dialog.manager.protocols import ManagedDialogAdapterProto, LaunchMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select, Row, SwitchTo, Back, Column, Start, Cancel
from aiogram_dialog.widgets.media import StaticMedia
from aiogram_dialog.widgets.text import Const, Format, Multi

from config import *
from DB import *

categories = {
    "Всем": ["<7", "8", "9", "10", "11", "12"],
    "Студентам": ["12"],
    "Школьникам": ["<7", "8", "9", "10", "11"]
}

class AdminSG(StatesGroup):
    admin = State()


class AnswerSG(StatesGroup):
    answer = State()
    ticket = State()
    check = State()


class PostSG(StatesGroup):
    post = State()
    to_who = State()
    check = State()


async def get_data(dialog_manager: DialogManager, **kwargs):
    return {
        'post': dialog_manager.current_context().dialog_data.get("post", None),
        'answer': dialog_manager.current_context().dialog_data.get("answer", None),
        'ticket': dialog_manager.current_context().dialog_data.get("ticket", None),
        'check': dialog_manager.current_context().dialog_data.get("check", None),
        'category': dialog_manager.current_context().dialog_data.get("category", None),
    }


async def admin(m: Message, dialog_manager: DialogManager):
    # it is important to reset stack because user wants to restart everything
    await dialog_manager.start(AdminSG.admin, mode=StartMode.RESET_STACK)


async def answer_handler(m: Message, dialog: Dialog, manager: DialogManager):
    for i in await Questions.filter().values_list("key",
                                                  flat=True):  # Находим в Бд все ключи вопросов и проверяем содержатся ли они в сообщении
        if m.text.find(str(i)) != -1:
            manager.current_context().dialog_data["answer"] = m.text.replace(str(i), "")
            manager.current_context().dialog_data["ticket"] = str(i)
            await manager.dialog().switch_to(AnswerSG.check)
            return
    await bot.send_message(m.chat.id, "Вопроса с таким номером не существует")
    await manager.start(AdminSG.admin, mode=StartMode.RESET_STACK)


async def post_handler(m: Message, dialog: Dialog, manager: DialogManager):
    manager.current_context().dialog_data["post"] = m.text
    await manager.dialog().switch_to(PostSG.to_who)


async def on_who_clicked(c: ChatEvent, select: Select, manager: DialogManager, item_id: str):
    manager.current_context().dialog_data["category"] = item_id
    await manager.dialog().switch_to(PostSG.check)


async def on_post_ok_clicked(c: CallbackQuery, button: Button, manager: DialogManager):
    for grade in categories[manager.current_context().dialog_data["category"]]:
        for user in await ActiveUsers.filter(grade=grade).values_list("user_id", flat=True):
            await bot.send_message(user,
                               manager.current_context().dialog_data["post"])
    await bot.send_message(CHAT_ID, "Пост отправлен")
    await manager.done()
    await manager.bg().done()


async def on_answer_ok_clicked(c: CallbackQuery, button: Button, manager: DialogManager):
    await bot.send_message(
        (await Questions.filter(key=manager.current_context().dialog_data["ticket"]).values_list("user_id_id",
                                                                                                 flat=True))[
            0], manager.current_context().dialog_data["answer"])
    # Находим в бд кому отправить сообщение, после чего - отправляем
    await Questions.filter(key=manager.current_context().dialog_data["ticket"]).update(is_answered=True)
    await bot.send_message(CHAT_ID, "Ответ отправлен")
    await manager.done()
    await manager.bg().done()


root_admin_dialog = Dialog(
    Window(
        Const("Hello, admin"),
        Start(Const("I want to answer"), id="an", state=AnswerSG.answer),
        Start(Const("I want to post"), id="po", state=PostSG.post),
        state=AdminSG.admin
    ),
    launch_mode=LaunchMode.ROOT
)

post_dialog = Dialog(
    Window(
        Const("Please, send post"),
        MessageInput(post_handler),
        Cancel(Const("⏪ Назад")),
        state=PostSG.post
    ),
    Window(
        Const("Кому отправить?"),
        Row(Select(
            Format("{item}"),
            items=["Школьникам",
                   "Студентам",
                   "Всем"
                   ],
            item_id_getter=lambda x: x,
            id="grades",
            on_click=on_who_clicked,
        )),
        Cancel(Const("⏪ Назад")),
        state=PostSG.to_who
    ),
    Window(
        Format('<b>Пожалуйста, проверьте корректность введённых данных</b>\n'
               '<b>Пост:</b> {post}\n'),
        Column(
            Button(Const("Всё верно! ✅"), id="yes", on_click=on_post_ok_clicked),
            Back(Const("⏪ Назад"))
        ),
        parse_mode=ParseMode.HTML,
        state=PostSG.check,
        getter=get_data
    ),
    launch_mode=LaunchMode.SINGLE_TOP
)

answer_dialog = Dialog(
    Window(
        Const("Please, answer"),
        MessageInput(answer_handler),
        Cancel(Const("⏪ Назад")),
        state=AnswerSG.answer
    ),
    Window(
        Format('<b>Пожалуйста, проверьте корректность введённых данных</b>\n'
               '<b>Тикет:</b> {ticket}\n'
               '<b>Ответ:</b> {answer}\n'),
        Column(
            Button(Const("Всё верно! ✅"), id="yes", on_click=on_answer_ok_clicked),
            Back(Const("⏪ Назад"))
        ),
        parse_mode=ParseMode.HTML,
        state=AnswerSG.check,
        getter=get_data
    ),
    launch_mode=LaunchMode.SINGLE_TOP
)
