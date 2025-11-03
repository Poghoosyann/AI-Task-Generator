import os
import asyncio
import httpx
import json

from aiogram import Dispatcher, Bot, types, F
from aiogram.client.default import DefaultBotProperties
from urllib.parse import unquote
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, CallbackQuery, BufferedInputFile, FSInputFile
from dotenv import load_dotenv

load_dotenv()
dp = Dispatcher()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "api", "db")

translations_file = "translations.json"
translations_data = {}

def load_translations(filepath):
    global translations_data
    with open(filepath, 'r', encoding='utf-8') as f:
        translations_data = json.load(f)
        
def get_translated_text(key, lang_code="en", **kwargs):
    translation_dict = translations_data.get(key, {})
    text = translation_dict.get(lang_code, translation_dict.get("en", ""))
    return text.format(**kwargs)

def is_button_text_for_key(message_text: str, key: str) -> bool:
    translations_for_key = translations_data.get(key, {})
    for translated_text in translations_for_key.values():
        if translated_text == message_text:
            return True
    return False

load_translations(translations_file)

async def keyboard_buttons(lang_code:str):
    button_user = KeyboardButton(text=get_translated_text("button_user", lang_code))
    button_history = KeyboardButton(text=get_translated_text("button_history", lang_code))
    button_projects = KeyboardButton(text=get_translated_text("button_projects", lang_code))
    button_help = KeyboardButton(text=get_translated_text("button_help", lang_code))
    button_settings = KeyboardButton(text=get_translated_text("button_settings", lang_code))
    button_request = KeyboardButton(text=get_translated_text("button_request", lang_code))

    keyboard_button_markup = ReplyKeyboardMarkup(
        keyboard=[
            [button_user, button_history, button_projects],
            [button_settings, button_request, button_help],
        ],
        resize_keyboard=True
    )
    return keyboard_button_markup

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    language_code = message.from_user.language_code if message.from_user.language_code else "en"

    user_data = {
        "telegram_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "language_code": language_code
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_KEY}/users", json=user_data)
        response.raise_for_status()

    choose_lang_text = get_translated_text("choose_language_text", language_code)

    button_en = InlineKeyboardButton(text="English", callback_data="set_lang:en") 
    button_ru = InlineKeyboardButton(text="Русский", callback_data="set_lang:ru")
    button_hy = InlineKeyboardButton(text="Հայերեն", callback_data="set_lang:hy")

    choose_language_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [button_en, button_ru, button_hy]
        ]
    )

    await message.answer(choose_lang_text, reply_markup=choose_language_markup)

@dp.callback_query(F.data.startswith("set_lang:"))
async def set_language_handler(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{API_KEY}/users/{user_id}/language", 
            json={"language_code": lang}
        )
        response.raise_for_status()

    welcome_text = get_translated_text("welcome_message", lang)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(welcome_text, reply_markup=await keyboard_buttons(lang))

    await callback.answer()

@dp.message(lambda message: is_button_text_for_key(message.text, "button_user"))
async def user_button_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = None
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()

    current_lang = user_data.get("language_code", "en") 

    username = user_data.get("username")
    first_name = user_data.get("first_name")
    last_name = user_data.get("last_name")
    language_code_from_db = user_data.get("language_code")
    
    profession = user_data.get("profession")
    level = user_data.get("level")
    specialization = user_data.get("specialization")

    null_text = get_translated_text("null_user", current_lang)

    user_text = (
        f"{get_translated_text('user_info_title', current_lang)}\n\n"
        f"{get_translated_text('username', current_lang)}: {username if username else null_text}\n"
        f"{get_translated_text('first_name', current_lang)}: {first_name if first_name else null_text}\n"
        f"{get_translated_text('last_name', current_lang)}: {last_name if last_name else null_text}\n"
        f"{get_translated_text('language_code', current_lang)}: {language_code_from_db if language_code_from_db else null_text}\n"
        f"{get_translated_text('profession', current_lang)}: {profession if profession else null_text}\n"
        f"{get_translated_text('level', current_lang)}: {level if level else null_text}\n"
        f"{get_translated_text('specialization', current_lang)}: {specialization if specialization else null_text}\n"
    )

    await message.answer(user_text)

@dp.message(lambda message: is_button_text_for_key(message.text, "button_projects"))
async def projects_button_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = None
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()

    current_lang = user_data.get("language_code", "en")

    project_text = get_translated_text("project_text", current_lang)

    await message.answer(project_text)

@dp.message(lambda message: is_button_text_for_key(message.text, "button_request"))
async def request_button_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = None
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()

    current_lang = user_data.get("language_code", "en")

    request_text = get_translated_text("request_btn_text", current_lang)

    await message.answer(request_text)

@dp.message(lambda message: is_button_text_for_key(message.text, "button_settings"))
async def settings_button_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = None

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()

    current_lang = user_data.get("language_code", "en")

    settings_text = get_translated_text("choose_language_text", current_lang)

    button_en = InlineKeyboardButton(text="English", callback_data="set_lang:en") 
    button_ru = InlineKeyboardButton(text="Русский", callback_data="set_lang:ru")
    button_hy = InlineKeyboardButton(text="Հայերեն", callback_data="set_lang:hy")

    settings_language = InlineKeyboardMarkup(
        inline_keyboard=[
            [button_en, button_ru, button_hy]
        ]
    )

    await message.answer(settings_text, reply_markup = settings_language)


@dp.message(lambda message: is_button_text_for_key(message.text, "button_help") or message.text == "/help")
async def help_button_or_command_handler(message: types.Message):
    user_id = message.from_user.id
    user_data = None

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json() 

    current_lang = user_data.get("language_code", "en")

    help_text = get_translated_text("help_cmd_btn_text", current_lang)

    await message.answer(help_text)

@dp.message(Command("choose_profession"))
async def set_profession(message: types.Message):
    user_id = message.from_user.id
    user_data = None

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json() 

    current_lang = user_data.get("language_code", "en")

    set_profession_text = get_translated_text("set_profession_text", current_lang)

    programmer_button = InlineKeyboardButton(text = get_translated_text("programmer_translated", current_lang), callback_data="choose_profession:programmer")
    desinger_button = InlineKeyboardButton(text = get_translated_text("desinger_translated", current_lang), callback_data="choose_profession:desinger")
    marketer_button = InlineKeyboardButton(text = get_translated_text("marketer_translated", current_lang), callback_data="choose_profession:marketer")

    profession_inline_button = InlineKeyboardMarkup(
        inline_keyboard = [
            [programmer_button],[desinger_button], [marketer_button]
        ]
    )

    await message.answer(set_profession_text, reply_markup = profession_inline_button)


@dp.callback_query(F.data.startswith("choose_profession:"))
async def handle_profession_choice(callback: CallbackQuery):
    profession = callback.data.split(":")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()
    current_lang = user_data.get("language_code", "en")

    await callback.message.edit_reply_markup(reply_markup=None)

    set_level_text = get_translated_text("set_level_text", current_lang)

    beginer_button = InlineKeyboardButton(text=get_translated_text("level_beginer_translated", current_lang), callback_data=f"choose_level:{profession}:beginer")
    experienced_button = InlineKeyboardButton(text=get_translated_text("level_experienced_translated", current_lang), callback_data=f"choose_level:{profession}:experienced")
    advanced_button = InlineKeyboardButton(text=get_translated_text("level_advanced_translated", current_lang), callback_data=f"choose_level:{profession}:advanced")

    level_inline_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [beginer_button], [experienced_button], [advanced_button]
        ]
    )
    
    await callback.message.answer(set_level_text, reply_markup=level_inline_markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("choose_level:"))
async def handle_level_choice(callback: CallbackQuery):
    _, profession, level = callback.data.split(":")
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()
    current_lang = user_data.get("language_code", "en")

    await callback.message.edit_reply_markup(reply_markup=None)

    text_message = get_translated_text("choose_specialization_text", current_lang)
    

    if profession == "programmer":
        buttons = [
            [InlineKeyboardButton(text=get_translated_text("specialization_python_fastapi", current_lang), callback_data=f"set_specialization:{profession}:{level}:Python(FastAPI)")],
            [InlineKeyboardButton(text=get_translated_text("specialization_python_telegram_bots", current_lang), callback_data=f"set_specialization:{profession}:{level}:Python(Telegram Bots)")],
            [InlineKeyboardButton(text=get_translated_text("specialization_python_django", current_lang), callback_data=f"set_specialization:{profession}:{level}:Python(Django)")],
            [InlineKeyboardButton(text=get_translated_text("specialization_vuejs", current_lang), callback_data=f"set_specialization:{profession}:{level}:Vue.js")],
            [InlineKeyboardButton(text=get_translated_text("specialization_nextjs", current_lang), callback_data=f"set_specialization:{profession}:{level}:Next.js")],
            [InlineKeyboardButton(text=get_translated_text("specialization_nodejs", current_lang), callback_data=f"set_specialization:{profession}:{level}:Node.js")]
        ]
    elif profession == "desinger":
        buttons = [
            [InlineKeyboardButton(text=get_translated_text("specialization_graphic_designer", current_lang), callback_data=f"set_specialization:{profession}:{level}:Graphic Designer")],
            [InlineKeyboardButton(text=get_translated_text("specialization_ui_ux_designer", current_lang), callback_data=f"set_specialization:{profession}:{level}:UI/UX Designer")],
            [InlineKeyboardButton(text=get_translated_text("specialization_web_designer", current_lang), callback_data=f"set_specialization:{profession}:{level}:Web Designer")],
            [InlineKeyboardButton(text=get_translated_text("specialization_motion_designer", current_lang), callback_data=f"set_specialization:{profession}:{level}:Motion Designer")]
        ]
    elif profession == "marketer":
        buttons = [
            [InlineKeyboardButton(text=get_translated_text("specialization_digital_marketing", current_lang), callback_data=f"set_specialization:{profession}:{level}:Digital Marketing")],
            [InlineKeyboardButton(text=get_translated_text("specialization_content_marketing", current_lang), callback_data=f"set_specialization:{profession}:{level}:Content Marketing")],
            [InlineKeyboardButton(text=get_translated_text("specialization_seo_specialist", current_lang), callback_data=f"set_specialization:{profession}:{level}:SEO Specialist")],
            [InlineKeyboardButton(text=get_translated_text("specialization_social_media_marketing", current_lang), callback_data=f"set_specialization:{profession}:{level}:Social Media Marketing")]
        ]

    specialization_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer(text_message, reply_markup=specialization_markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("set_specialization:"))
async def handle_specialization_choice(callback: CallbackQuery):
    _, profession, level, specialization = callback.data.split(":")
    user_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json() 

    current_lang = user_data.get("language_code", "en")

    profession_level_data = {
        "profession": profession,
        "level": level,
        "specialization": specialization
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{API_KEY}/users/{user_id}/profession_level",
            json=profession_level_data
        )
        response.raise_for_status()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(get_translated_text("profession_level_set_success", current_lang))
    await callback.answer()


@dp.message(Command("get_project"))
async def get_project_cmd(message: types.Message):
    user_id = message.from_user.id
    user_data = None
    
    async with httpx.AsyncClient(timeout=500.0) as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()


    current_lang = user_data.get("language_code", "en")
    
    if user_data.get("current_project_id"):
        await message.answer(get_translated_text("already_have_project", current_lang))
        return

    if not user_data.get("profession") or not user_data.get("level") or not user_data.get("specialization"):
        await message.answer(get_translated_text("set_info_first", current_lang))
        return
        
    await message.answer(get_translated_text("get_project_text", current_lang))
    
    profession = user_data["profession"]
    level = user_data["level"]
    specialization = user_data["specialization"]

    async with httpx.AsyncClient(timeout=500.0) as http_client:
            response = await http_client.post(
                f"{API_KEY}/projects/get_project",
                json={
                    "telegram_id": user_id,
                    "profession": profession,
                    "level": level,
                    "specialization": specialization,
                    "language_code": current_lang
                }
            )
            response.raise_for_status() 

            pdf_file_binary = await response.aread()
            
            project_title = unquote(response.headers.get("X-Project-Title", "Сгенерированный план проекта"))
            project_description = unquote(response.headers.get("X-Project-Description", "Подробное описание проекта."))
            project_id = response.headers.get("X-Project-Id", "unknown")

            final_text = get_translated_text("new_project_details", current_lang, title=f"<b>{project_title}</b>", description=project_description)
            await message.answer(final_text, parse_mode=ParseMode.HTML)
            
            pdf_file_name = f"project_{project_id}.pdf"
            await message.answer_document(BufferedInputFile(pdf_file_binary, filename=pdf_file_name)) 


@dp.message(Command("project"))
async def check_project(message: types.Message):
    user_id = message.from_user.id
    user_data = None
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_KEY}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()


    current_lang = user_data.get("language_code", "en")
    current_project_id = user_data.get("current_project_id")
    project_title = user_data.get("current_project_title")
    project_desc = user_data.get("current_project_description")

    if not current_project_id:
        await message.answer(get_translated_text("no_have_project", current_lang))
        return

    

    elif current_project_id:
        project_title = user_data.get("current_project_title")
        project_desc = user_data.get("current_project_description")
        pdf_path = user_data.get("current_project_pdf_path")


        full_pdf_path = os.path.join(DB_DIR, pdf_path)

        await message.answer(f"📌 <b>{project_title}</b>\n\n{project_desc}", parse_mode="HTML")

        if os.path.exists(full_pdf_path):
            await message.answer_document(types.FSInputFile(full_pdf_path))
        else:
            await message.answer(get_translated_text("failed_to_send_pdf", current_lang))


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())