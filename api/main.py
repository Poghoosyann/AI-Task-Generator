import os
import asyncio
import re 

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from starlette.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, HTTPException, Response, status 
from datetime import datetime
from urllib.parse import quote
from weasyprint import HTML 
from bson import ObjectId 

load_dotenv()

MONGO_DB = os.getenv("MONGO_DB")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client()
model_id = "gemini-2.5-flash"

mongo_client = AsyncIOMotorClient(MONGO_DB)
db = mongo_client.get_database("PracticeBot")

app = FastAPI()

BASE_PROJECT_DIR = os.path.join("..", "api", "db")

class UserData(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    profession: str | None = None
    level: str | None = None
    specialization: str | None = None
    current_project_id: str | None = None

class UserLanguageUpdate(BaseModel):
    language_code: str

class UserUpdateProfessionLevel(BaseModel):
    profession: str
    level: str
    specialization: Optional[str] = None

class UserUpdate(BaseModel):
    current_project_id: Optional[str] = Field(None, alias="current_project_id")

class UserUpdateData(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    profession: Optional[str] = None
    level: Optional[str] = None
    specialization: Optional[str] = None

class ProjectRequestData(BaseModel):
    telegram_id: int
    profession: str
    level: str
    specialization: str
    language_code: str

async def getUser(user_id: int):
    users_collection = db.users
    user = await users_collection.find_one({"_id": user_id})
    return user

async def updateUser(telegram_id: int, update_data: Dict[str, Any]):
    users_collection = db.users
    result = await users_collection.update_one(
        {"_id": telegram_id},
        update_data
    )

@app.post("/users", status_code=status.HTTP_200_OK)
async def create_user(user: UserData):
    users_collection = db.users

    user_data_dict = user.model_dump(exclude_unset=True)
    user_data_dict["_id"] = user.telegram_id 
    
    result = await users_collection.update_one(
        {"_id": user.telegram_id}, 
        {"$set": user_data_dict},
        upsert=True
    )
    
    return {"message": "Пользователь создан или обновлен", "telegram_id": user.telegram_id}


@app.get("/users/{telegram_id}", response_model=UserData)
async def get_user_data(telegram_id: int):
    user = await getUser(telegram_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    user['telegram_id'] = user['_id']
    return UserData(**user)

    
@app.patch("/users/{telegram_id}/language", status_code=status.HTTP_200_OK)
async def update_user_language(telegram_id: int, lang_update: UserLanguageUpdate):
    await updateUser(
        telegram_id,
        {"$set": {"language_code": lang_update.language_code}}
    )
    return {"message": "Попытка обновления языка пользователя завершена"}

@app.patch("/users/{telegram_id}/profession_level", status_code=status.HTTP_200_OK)
async def update_profession_level(telegram_id: int, profession_level: UserUpdateProfessionLevel):
    await updateUser(
        telegram_id,
        {"$set": {
            "profession": profession_level.profession,
            "level": profession_level.level,
            "specialization": profession_level.specialization
        }}
    )
    return {"message": "Профессия и уровень пользователя обновлены"}


@app.post("/projects/get_project")
async def get_project_for_user(request_data: ProjectRequestData):
    user_data = await getUser(request_data.telegram_id)
    if user_data and user_data.get("current_project_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У пользователя уже есть активный проект. Пожалуйста, завершите его, прежде чем брать новый.")
    
    prompt_text = (
        f"Ты — опытный наставник по обучению. Мне нужен детальный план проекта для пользователя, который "
        f"выбрал профессию '{request_data.profession}', уровень '{request_data.level}', "
        f"и специализацию '{request_data.specialization}'. "
        f"Язык проекта: '{request_data.language_code}'.\n\n"
        f"Сгенерируй HTML-код полноценного описания проекта, который будет состоять примерно из 5 страниц A4. "
        f"Включи в него следующие разделы:\n"
        f"1.  **Название проекта** (Title): Должно быть в теге <title> и <h1>.\n"
        f"2.  **Описание проекта** (Project Description): Что нужно сделать, цель проекта. Должно быть в первом <p> после <h1>.\n"
        f"3.  **Задачи проекта** (Tasks): Подробный список задач, которые нужно выполнить, пошагово.\n"
        f"4.  **Что нужно изучить** (What to learn): Необходимые технологии, инструменты, концепции.\n"
        f"5.  **Ресурсы для изучения** (Learning Resources): Примеры ссылок на документацию, учебники, статьи (указывай только названия и типы ресурсов, без реальных URL, так как это генерируемый контент).\n"
        f"6.  **Критерии успеха** (Success Criteria): Как будет оцениваться выполнение проекта.\n"
        f"7.  **Ожидаемый результат** (Expected Outcome): Что пользователь получит после завершения проекта.\n\n"
        f"Используй семантические HTML5 теги (`<header>`, `<main>`, `<footer>`, `<section>`, `<article>`). "
        f"Примени базовые стили CSS, чтобы PDF выглядел аккуратно и профессионально (используй тег `<style>` внутри `<head>`). "
        f"Убедись, что текст хорошо читаем, разбит на абзацы и списки. "
        f"Стилизуй заголовки, параграфы и списки. Добавь отступы и выравнивание. "
        f"Важно: HTML должен быть самодостаточным и не должен содержать внешних ссылок на CSS или JS."
    )

    generated_html = ""
    response = await client.aio.models.generate_content(
    model=model_id,
    contents=prompt_text,
)
    generated_html = response.text
    
    project_title = "Сгенерированный план проекта"
    project_description = "Подробное описание проекта."
    
    title_match = re.search(r'<title>(.*?)</title>', generated_html, re.IGNORECASE | re.DOTALL)
    if title_match:
        project_title = title_match.group(1).strip()
    
    description_match = re.search(r'<h1>.*?</h1>\s*<p>(.*?)</p>', generated_html, re.IGNORECASE | re.DOTALL)
    if description_match:
        project_description = description_match.group(1).strip()
    elif re.search(r'<p>(.*?)</p>', generated_html, re.IGNORECASE | re.DOTALL):
        project_description = re.search(r'<p>(.*?)</p>', generated_html, re.IGNORECASE | re.DOTALL).group(1).strip()


    pdf_file_binary = b""
    try:
        pdf_file_binary = await asyncio.to_thread(HTML(string=generated_html).write_pdf)
    except Exception as e:
        print(f"Ошибка при конвертации HTML в PDF: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при создании PDF: {str(e)}")


    new_project_id = ObjectId()
    
    user_project_dir = os.path.join(BASE_PROJECT_DIR, str(request_data.telegram_id))
    os.makedirs(user_project_dir, exist_ok=True)

    pdf_filename = f"project_{new_project_id}.pdf"
    pdf_filepath = os.path.join(user_project_dir, pdf_filename)

    try:
        with open(pdf_filepath, "wb") as f:
            f.write(pdf_file_binary)
    except IOError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при сохранении PDF на диск: {str(e)}")

    project_info_for_user = {
        "current_project_id": str(new_project_id),
        "current_project_status": "in_progress",
        "current_project_pdf_name": pdf_filename,
        "current_project_pdf_path": pdf_filepath,
        "current_project_title": project_title,
        "current_project_description": project_description,
        "current_project_profession": request_data.profession,
        "current_project_level": request_data.level,
        "current_project_specialization": request_data.specialization,
        "current_project_created_at": datetime.now()
    }

    await updateUser(
        request_data.telegram_id,
        {"$set": project_info_for_user}
    )
    
    return Response(content=pdf_file_binary, media_type="application/pdf", headers={
        "X-Project-Title": quote(project_title),
        "X-Project-Description": quote(project_description),
        "X-Project-Id": str(new_project_id)
    })
