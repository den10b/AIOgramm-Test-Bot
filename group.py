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


class AdminSG(StatesGroup):
    admin = State()


class AnswerSG(StatesGroup):
    answer = State()
    ticket = State()
    check = State()
    final = State()


class PostSG(StatesGroup):
    post = State()
    check = State()
    final = State()


async def get_data(dialog_manager: DialogManager, **kwargs):
    return {
        'post': dialog_manager.current_context().dialog_data.get("post", None),
        'answer': dialog_manager.current_context().dialog_data.get("answer", None),
        'ticket': dialog_manager.current_context().dialog_data.get("ticket", None),
        'check': dialog_manager.current_context().dialog_data.get("check", None),
    }


async def admin(m: Message, dialog_manager: DialogManager):
    # it is important to reset stack because user wants to restart everything
    await dialog_manager.start(AdminSG.admin, mode=StartMode.RESET_STACK)


async def answer_handler(m: Message, dialog: Dialog, manager: DialogManager):
    keys = DATA.keys()
    for i in keys:
        if m.text.find(str(i)) != -1:
            # await bot.send_message(DATA[i],)
            manager.current_context().dialog_data["answer"] = m.text.replace(str(i), "")
            manager.current_context().dialog_data["ticket"] = str(i)
            await manager.dialog().switch_to(AnswerSG.check)
            return
    await bot.send_message(m.chat.id, "Вопроса с таким номером не существует")
    await manager.start(AdminSG.admin, mode=StartMode.RESET_STACK)


async def post_handler(m: Message, dialog: Dialog, manager: DialogManager):
    manager.current_context().dialog_data["post"] = m.text
    await manager.dialog().switch_to(PostSG.check)


async def on_post_ok_clicked(c: CallbackQuery, button: Button, manager: DialogManager):
    for usr in ACTIVE_USERS:
        await bot.send_message(usr, manager.current_context().dialog_data["post"])
    await manager.dialog().switch_to(PostSG.final)


async def on_answer_ok_clicked(c: CallbackQuery, button: Button, manager: DialogManager):
    await bot.send_message(DATA[manager.current_context().dialog_data["ticket"]],
                           manager.current_context().dialog_data["answer"])
    await manager.dialog().switch_to(AnswerSG.final)

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
    Window(
        Const('Запись внесена!'),
        state=PostSG.final
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
    Window(
        Const('Запись внесена!'),
        state=AnswerSG.final
    ),
    launch_mode=LaunchMode.SINGLE_TOP
)