import asyncio
import logging
from datetime import datetime, time
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
from pathlib import Path
import os
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = str(os.getenv("BOT_TOKEN"))
print(BOT_TOKEN)

# Вопросы для опроса
QUESTIONS = [
    "Что ты сделал(а) для питомца сегодня?",
    "Было ли что-то трудным и неудобным с питомцем?",
    "Что сегодня порадовало тебя или питомца или расстроило?"
]

# Временная зона Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Время отправки опроса (19:00 по Москве)
SURVEY_TIME = time(19, 0)

# FSM состояния
class SurveyStates(StatesGroup):
    waiting_for_answer = State()

class RegistrationStates(StatesGroup):
    waiting_for_pet_type = State()
    waiting_for_pet_name = State()
    waiting_for_pet_age = State()

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище данных пользователей
DATA_FILE = Path("user_data.json")

def load_user_data():
    """Загрузка данных пользователей из файла"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    """Сохранение данных пользователей в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Глобальное хранилище
user_data = load_user_data()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = str(message.from_user.id)
    
    if user_id not in user_data:
        user_data[user_id] = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "pet_info": None,
            "surveys": []
        }
        save_user_data(user_data)
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я буду отправлять тебе опрос о твоём питомце каждый день в 19:00 по московскому времени.\n\n"
        "Команды:\n"
        "/start - Начать работу с ботом\n"
        "/survey - Пройти опрос сейчас\n"
        "/history - Посмотреть историю ответов\n"
        "/pet - Посмотреть информацию о питомце\n"
        "/editpet - Изменить информацию о питомце\n"
        "/stop - Отписаться от ежедневных опросов"
    )

@dp.message(Command("survey"))
async def cmd_survey(message: types.Message, state: FSMContext):
    """Начать опрос вручную"""
    user_id = str(message.from_user.id)
    
    # Проверяем, зарегистрирован ли питомец
    if user_id not in user_data or user_data[user_id].get("pet_info") is None:
        await start_registration(message.from_user.id, state)
    else:
        await start_survey(message.from_user.id, state)

@dp.message(Command("pet"))
async def cmd_pet(message: types.Message):
    """Показать информацию о питомце"""
    user_id = str(message.from_user.id)
    
    if user_id not in user_data or user_data[user_id].get("pet_info") is None:
        await message.answer("У тебя ещё не зарегистрирован питомец. Используй /survey для начала.")
        return
    
    pet = user_data[user_id]["pet_info"]
    await message.answer(
        f"🐾 Твой питомец:\n\n"
        f"Вид: {pet['type']}\n"
        f"Имя: {pet['name']}\n"
        f"Возраст: {pet['age']}"
    )

@dp.message(Command("editpet"))
async def cmd_editpet(message: types.Message, state: FSMContext):
    """Изменить информацию о питомце"""
    await start_registration(message.from_user.id, state)

@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    """Показать историю ответов"""
    user_id = str(message.from_user.id)
    
    if user_id not in user_data or not user_data[user_id]["surveys"]:
        await message.answer("У тебя пока нет сохранённых ответов.")
        return
    
    surveys = user_data[user_id]["surveys"]
    history_text = "📊 История твоих ответов:\n\n"
    
    for i, survey in enumerate(reversed(surveys[-10:]), 1):  # Последние 10
        history_text += f"📅 {survey['date']}\n"
        for j, answer in enumerate(survey['answers'], 1):
            history_text += f"{j}. {answer}\n"
        history_text += "\n"
    
    await message.answer(history_text)

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    """Отписаться от опросов"""
    user_id = str(message.from_user.id)
    
    if user_id in user_data:
        del user_data[user_id]
        save_user_data(user_data)
        await message.answer("Ты отписался от ежедневных опросов. Используй /start, чтобы снова подписаться.")
    else:
        await message.answer("Ты и так не подписан на опросы.")

async def start_registration(user_id: int, state: FSMContext):
    """Начать регистрацию питомца"""
    await state.set_state(RegistrationStates.waiting_for_pet_type)
    await bot.send_message(
        user_id,
        "🐾 Давай познакомимся с твоим питомцем!\n\n"
        "Вопрос 1 из 3:\nКакой у тебя питомец? (например: кошка, собака, хомяк, попугай)"
    )

@dp.message(RegistrationStates.waiting_for_pet_type)
async def process_pet_type(message: types.Message, state: FSMContext):
    """Обработка типа питомца"""
    await state.update_data(pet_type=message.text)
    await state.set_state(RegistrationStates.waiting_for_pet_name)
    await message.answer("Вопрос 2 из 3:\nКак зовут твоего питомца?")

@dp.message(RegistrationStates.waiting_for_pet_name)
async def process_pet_name(message: types.Message, state: FSMContext):
    """Обработка имени питомца"""
    await state.update_data(pet_name=message.text)
    await state.set_state(RegistrationStates.waiting_for_pet_age)
    await message.answer("Вопрос 3 из 3:\nСколько лет твоему питомцу? (можно примерно)")

@dp.message(RegistrationStates.waiting_for_pet_age)
async def process_pet_age(message: types.Message, state: FSMContext):
    """Обработка возраста питомца и завершение регистрации"""
    data = await state.get_data()
    user_id = str(message.from_user.id)
    
    # Сохраняем информацию о питомце
    if user_id not in user_data:
        user_data[user_id] = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "surveys": []
        }
    
    user_data[user_id]["pet_info"] = {
        "type": data['pet_type'],
        "name": data['pet_name'],
        "age": message.text
    }
    save_user_data(user_data)
    
    await message.answer(
        f"✅ Отлично! Информация сохранена:\n\n"
        f"🐾 {data['pet_type']}\n"
        f"📝 Имя: {data['pet_name']}\n"
        f"🎂 Возраст: {message.text}\n\n"
        f"Теперь начнём ежедневный опрос!"
    )
    
    # Переходим к опросу
    await state.clear()
    await start_survey(int(user_id), state)

async def start_survey(user_id: int, state: FSMContext):
    """Начать опрос для пользователя"""
    await state.update_data(
        current_question=0,
        answers=[],
        user_id=user_id
    )
    await state.set_state(SurveyStates.waiting_for_answer)
    
    await bot.send_message(
        user_id,
        f"🐾 Время ежедневного опроса о питомце!\n\n"
        f"Вопрос 1 из {len(QUESTIONS)}:\n{QUESTIONS[0]}"
    )

@dp.message(SurveyStates.waiting_for_answer)
async def process_answer(message: types.Message, state: FSMContext):
    """Обработка ответа на вопрос"""
    data = await state.get_data()
    current_question = data['current_question']
    answers = data['answers']
    
    # Сохраняем ответ
    answers.append(message.text)
    
    # Переходим к следующему вопросу
    current_question += 1
    
    if current_question < len(QUESTIONS):
        # Ещё есть вопросы
        await state.update_data(
            current_question=current_question,
            answers=answers
        )
        await message.answer(
            f"Вопрос {current_question + 1} из {len(QUESTIONS)}:\n{QUESTIONS[current_question]}"
        )
    else:
        # Опрос завершён
        user_id = str(message.from_user.id)
        
        # Сохраняем результаты
        survey_data = {
            "date": datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M"),
            "answers": answers
        }
        
        if user_id not in user_data:
            user_data[user_id] = {
                "username": message.from_user.username,
                "first_name": message.from_user.first_name,
                "surveys": []
            }
        
        user_data[user_id]["surveys"].append(survey_data)
        save_user_data(user_data)
        
        await message.answer(
            "✅ Спасибо за ответы! Твои данные сохранены.\n"
            "До завтра! 🐾"
        )
        await state.clear()

async def send_daily_survey():
    """Отправка ежедневного опроса всем пользователям"""
    logger.info("Отправка ежедневного опроса...")
    
    for user_id in list(user_data.keys()):
        try:
            # Проверяем, есть ли информация о питомце
            if user_data[user_id].get("pet_info") is None:
                # Если питомец не зарегистрирован, начинаем регистрацию
                state = dp.fsm.get_context(bot, user_id=int(user_id), chat_id=int(user_id))
                await start_registration(int(user_id), state)
            else:
                # Если питомец зарегистрирован, отправляем опрос
                state = dp.fsm.get_context(bot, user_id=int(user_id), chat_id=int(user_id))
                await start_survey(int(user_id), state)
            await asyncio.sleep(1)  # Задержка между отправками
        except Exception as e:
            logger.error(f"Ошибка при отправке опроса пользователю {user_id}: {e}")

async def scheduler():
    """Планировщик для отправки опросов в заданное время"""
    while True:
        now = datetime.now(MOSCOW_TZ)
        target_time = now.replace(hour=SURVEY_TIME.hour, minute=SURVEY_TIME.minute, second=0, microsecond=0)
        
        if now >= target_time:
            # Если время уже прошло сегодня, планируем на завтра
            target_time = target_time.replace(day=target_time.day + 1)
        
        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"Следующий опрос через {sleep_seconds / 3600:.1f} часов в {target_time}")
        
        await asyncio.sleep(sleep_seconds)
        await send_daily_survey()

async def main():
    """Главная функция запуска бота"""
    # Создаём задачу для планировщика
    asyncio.create_task(scheduler())
    
    # Запускаем бота
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())