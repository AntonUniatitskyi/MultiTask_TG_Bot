import asyncio
import logging
import aiohttp
import sqlite3
import requests
import json
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from decouple import config

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ТОКЕНЫ ---
TOKEN = config('TOKEN')
WEATHER_TOKEN = config('WEATHER_TOKEN')
GITHUB_TOKEN = config('GITHUB_TOKEN')
ALARM_API_TOKEN = config('ALARM_API_TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_PATH = 'plans.db'

# --- БД ---
def create_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        conn.commit()
        logger.info("Таблица 'plans' успешно создана или уже существует")

def greate_db_user():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        region_id TEXT,
        reg_id INTEGER
    )
    """)
    conn.commit()

def get_db_connection():
    conn = sqlite3.connect('bot_data.db')  # Укажите путь к вашей базе данных
    return conn

def save_plan(user_id, plan_text):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        cursor.execute('INSERT INTO plans (user_id, plan) VALUES (?, ?)', (user_id, plan_text))
        conn.commit()

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Планы")],
            [KeyboardButton(text="🌦 Прогноз погоды")],
            [KeyboardButton(text="🐙 GitHub Коммиты")],
            [KeyboardButton(text="🚨 Уведомления о тревогах")]
        ],
        resize_keyboard=True
    )

# --- ХЕАДЕР ---
token = config('ALARM_API_TOKEN')
header = {
    'Authorization': f'{token}',
    'Content-Type': 'application/json'
}

url = 'https://api.ukrainealarm.com/api/v3/regions'
url_alert = 'https://api.ukrainealarm.com/api/v3/alerts'

# --- СОСТОЯНИЯ ---
class WeatherState(StatesGroup):
    waiting_for_city = State()

class RegionState(StatesGroup):
    waiting_for_obl = State()
    waiting_for_regi = State()
    waiting_for_city = State()

class PlanState(StatesGroup):
    waiting_for_plan = State()
    waiting_for_plan_edit = State()
    waiting_for_new_plan = State()
    waiting_for_plan_delete = State()

class GitHubState(StatesGroup):
    waiting_for_owner = State()
    waiting_for_repo = State()

# --- ПОГОДНЫЕ УСЛОВИЯ ---
WEATHER_CONDITIONS = {
    "Sunny": "Солнечно",
    "Clear": "Ясно",
    "Partly cloudy": "Переменная облачность",
    "Cloudy": "Облачно",
    "Overcast": "Пасмурно",
    "Mist": "Туман",
    "Patchy rain possible": "Возможен небольшой дождь",
    "Patchy snow possible": "Возможен небольшой снег",
    "Patchy sleet possible": "Возможен небольшой дождь со снегом",
    "Patchy freezing drizzle possible": "Возможен небольшой ледяной дождь",
    "Thundery outbreaks possible": "Возможны грозы",
    "Blowing snow": "Метель",
    "Blizzard": "Сильная метель",
    "Fog": "Густой туман",
    "Freezing fog": "Ледяной туман",
    "Light drizzle": "Лёгкая морось",
    "Heavy rain": "Сильный дождь",
    "Light rain": "Лёгкий дождь",
    "Moderate rain": "Умеренный дождь",
    "Heavy snow": "Сильный снег",
    "Light snow": "Лёгкий снег",
    "Moderate snow": "Умеренный снег",
    "Light rain shower": "Лёгкий ливень",
    "Moderate or heavy rain shower": "Умеренный или сильный ливень",
    "Light snow showers": "Лёгкие снежные осадки",
    "Moderate or heavy snow showers": "Умеренные или сильные снежные осадки",
    "Ice pellets": "Ледяные гранулы",
    "Rain": "Дождь",
    "Snow": "Снег",
    "Sleet": "Дождь со снегом",
    "Patchy rain nearby": "Небольшой дождь поблизости"
}

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=main_menu())

# --- ПОГОДА ---
@dp.message(lambda message: message.text == "🌦 Прогноз погоды")
async def pogoda(message: types.Message, state: FSMContext):
    await message.answer("Введите пожалуйста город для просмотра прогноза", reply_markup=main_menu())
    await state.set_state(WeatherState.waiting_for_city)

async def get_weather(city):
    url = f"https://api.weatherapi.com/v1/forecast.json?key={WEATHER_TOKEN}&q={city}&days=3&aqi=yes"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    city_name = data["location"]["name"]
                    temp = data["current"]["temp_c"]
                    condition = data["current"]["condition"]["text"]
                    wind = data["current"]["wind_kph"]
                    humidity = data["current"]["humidity"]
                    condition_ru = WEATHER_CONDITIONS.get(condition, condition)
                    current_weather = (f"Погода в {city_name} сейчас:\n"
                                       f"\n"
                                       f"🌡️Температура - {temp}°C\n"
                                       f"\n"
                                       f"🔅Состояние - {condition_ru}\n"
                                       f"\n"
                                       f"🪁Ветер - {wind} км/ч\n"
                                       f"\n"
                                       f"🌧️Влажность - {humidity}%")

                    forecast_days = data["forecast"]["forecastday"]
                    forecast_text = "Прогноз на следующие дни:\n"
                    for day in forecast_days[1:]:
                        date = day["date"]
                        max_temp = day["day"]["maxtemp_c"]
                        min_temp = day["day"]["mintemp_c"]
                        condition = day["day"]["condition"]["text"]
                        condition_ru = WEATHER_CONDITIONS.get(condition, condition)
                        forecast_text += (f"🗓️{date}:\n"
                                         f"🌡️Температура -> {min_temp}°C - {max_temp}°C\n"
                                         f"🔅Состояние -> {condition_ru}\n\n")

                    return current_weather, forecast_text
                else:
                    error_msg = f"Ошибка {response.status}: "
                    if response.status == 400:
                        error_msg += "Неверный запрос, проверьте название города."
                    elif response.status == 401:
                        error_msg += "Проблема с API-ключом."
                    return error_msg, None
    except Exception as e:
        logger.error(f"Ошибка при запросе погоды: {e}")
        return f"Произошла ошибка: {str(e)}", None

@dp.message(WeatherState.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text.strip()
    if not city:
        await message.answer("Вы не ввели город. Пожалуйста, введите название города.")
        return
    if not all(c.isalpha() or c in " -—" for c in city):
        await message.answer("Название города может содержать только буквы, пробелы или дефисы.")
        return

    current_weather, forecast_text = await get_weather(city)
    await message.answer(current_weather, reply_markup=main_menu())
    if forecast_text:
        await message.answer(forecast_text, reply_markup=main_menu())
    await state.clear()

# --- ПЛАНЫ ---
@dp.message(lambda message: message.text == "📅 Планы")
async def plan(message: types.Message, state: FSMContext):
    plan_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕Добавить план")],
            [KeyboardButton(text="✏️Изменить план")],
            [KeyboardButton(text="🗑️Удалить план")],
            [KeyboardButton(text="📋Список планов")],
            [KeyboardButton(text="🔙Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите действие с планами:", reply_markup=plan_menu)

@dp.message(lambda message: message.text == "🔙Назад")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await message.answer("Выберите действие:", reply_markup=main_menu())
    await state.clear()

@dp.message(lambda message: message.text == "➕Добавить план")
async def add_plan(message: types.Message, state: FSMContext):
    await message.answer("Введите текст для нового плана:", reply_markup=main_menu())
    await state.set_state(PlanState.waiting_for_plan)

@dp.message(PlanState.waiting_for_plan)
async def process_plan(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    plan_text = message.text.strip()
    if not plan_text:
        await message.answer("Вы не ввели текст плана. Пожалуйста, попробуйте снова.")
        return

    save_plan(user_id, plan_text)
    await message.answer(f"Ваш план '{plan_text}' успешно добавлен.", reply_markup=main_menu())
    await state.clear()

@dp.message(lambda message: message.text == "✏️Изменить план")
async def edit_plan(message: types.Message, state: FSMContext):
    await message.answer("Введите ID плана, который хотите изменить:", reply_markup=main_menu())
    await state.set_state(PlanState.waiting_for_plan_edit)

@dp.message(PlanState.waiting_for_plan_edit)
async def process_plan_edit(message: types.Message, state: FSMContext):
    plan_id = message.text.strip()
    if not plan_id.isdigit():
        await message.answer("ID плана должен быть числом. Попробуйте снова.", reply_markup=main_menu())
        return
    plan_id = int(plan_id)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        cursor.execute("SELECT id, plan FROM plans WHERE id = ? AND user_id = ?", (plan_id, message.from_user.id))
        plan = cursor.fetchone()

    if not plan:
        await message.answer(f"План с ID {plan_id} не найден. Пожалуйста, проверьте ID и попробуйте снова.",
                             reply_markup=main_menu())
        return

    await message.answer(f"Текущий план: {plan[1]}\n\nВведите новый текст для плана:", reply_markup=main_menu())
    await state.set_state(PlanState.waiting_for_new_plan)
    await state.update_data(plan_id=plan_id)

@dp.message(PlanState.waiting_for_new_plan)
async def process_new_plan(message: types.Message, state: FSMContext):
    new_plan_text = message.text.strip()
    if not new_plan_text:
        await message.answer("Вы не ввели новый текст плана. Попробуйте снова.", reply_markup=main_menu())
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        cursor.execute("UPDATE plans SET plan = ? WHERE id = ? AND user_id = ?",
                       (new_plan_text, plan_id, message.from_user.id))
        conn.commit()

    await message.answer(f"План с ID {plan_id} успешно обновлён на: '{new_plan_text}'.", reply_markup=main_menu())
    await state.clear()

@dp.message(lambda message: message.text == "🗑️Удалить план")
async def delete_plan(message: types.Message, state: FSMContext):
    await message.answer("Введите ID плана, который хотите удалить:", reply_markup=main_menu())
    await state.set_state(PlanState.waiting_for_plan_delete)

@dp.message(PlanState.waiting_for_plan_delete)
async def process_plan_delete(message: types.Message, state: FSMContext):
    plan_id = message.text.strip()
    if not plan_id.isdigit():
        await message.answer("ID плана должен быть числом. Попробуйте снова.", reply_markup=main_menu())
        return
    plan_id = int(plan_id)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        cursor.execute("DELETE FROM plans WHERE id = ? AND user_id = ?", (plan_id, message.from_user.id))
        affected_rows = cursor.rowcount
        conn.commit()

    if affected_rows > 0:
        await message.answer(f"План с ID {plan_id} успешно удалён.", reply_markup=main_menu())
    else:
        await message.answer(f"План с ID {plan_id} не найден.", reply_markup=main_menu())
    await state.clear()

@dp.message(lambda message: message.text == "📋Список планов")
async def list_plans(message: types.Message, state: FSMContext):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL
            )
        ''')
        cursor.execute("SELECT id, plan FROM plans WHERE user_id = ?", (message.from_user.id,))
        plans = cursor.fetchall()

    if not plans:
        await message.answer("У вас пока нет планов.", reply_markup=main_menu())
    else:
        response = "Ваши планы:\n"
        for plan in plans:
            plan_items = plan[1].split(", ")
            formatted_plan = "\n    ".join(plan_items)
            response += f"ID: {plan[0]}\n    {formatted_plan}\n\n"
        await message.answer(response, reply_markup=main_menu())

# --- GITHUB КОММИТЫ ---
@dp.message(lambda message: message.text == "🐙 GitHub Коммиты")
async def github_commits(message: types.Message, state: FSMContext):
    await message.answer("Введите имя владельца репозитория (например, torvalds):")
    await state.set_state(GitHubState.waiting_for_owner)

@dp.message(GitHubState.waiting_for_owner)
async def process_owner(message: types.Message, state: FSMContext):
    await state.update_data(owner=message.text.strip())
    await message.answer("Теперь введите название репозитория (например, linux):")
    await state.set_state(GitHubState.waiting_for_repo)

@dp.message(GitHubState.waiting_for_repo)
async def process_repo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    owner = data.get("owner")
    repo = message.text.strip()
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            commits = response.json()
            if commits:
                commit_messages = "\n".join(
                    [f"👤 {commit['commit']['author']['name']}: {commit['commit']['message']}" for commit in commits[:5]]
                )
                await message.answer(f"Последние коммиты в репозитории {owner}/{repo}:\n{commit_messages}")
            else:
                await message.answer("В этом репозитории пока нет коммитов.")
        else:
            await message.answer(f"Ошибка: {response.status_code}. Проверьте имя владельца и репозитория.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")
    await state.clear()


# --- ТРЕВОГА ---
@dp.message(lambda message: message.text == "🚨 Уведомления о тревогах")
async def select_region(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT region_id FROM users WHERE user_id = ?", (user_id,))
    region = cursor.fetchone()

    # Если регион найден, показываем кнопки для проверки тревоги
    if region:
        region_id = region[0]
        alert_menu = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔙 Назад")],
                [KeyboardButton(text="🔔 Проверить сейчас")],
                [KeyboardButton(text="✏️ Изменить регион")],
            ],
            resize_keyboard=True
        )
        await message.answer(f"Вы подписаны на уведомления о тревогах в регионе: {region_id}\nВыберите действие:", reply_markup=alert_menu)
    else:
        await message.answer("Вы не выбрали регион для уведомлений. Пожалуйста, введите регион.", reply_markup=main_menu())
    
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=header) as response:
                    if response.status == 200:
                        data = await response.json()

                        with open("data.json", "w", encoding="utf-8") as file:
                            json.dump(data, file, indent=4, ensure_ascii=False)

                        # Обходим все регионы
                        if 'states' in data:
                            regions_text = "\n\n".join(f"<code>{obl['regionName']}</code>" for obl in data['states'])
                            await message.answer(regions_text, parse_mode="HTML", reply_markup=main_menu())
                            await message.answer("Пожалуйста, введите область. Нажмите на область для копирования", reply_markup=main_menu())
                        else:
                            await message.answer("Ошибка: Данные о регионах отсутствуют.")
                    else:
                        await message.answer(f"Ошибка API: {response.status}")
        except Exception as e:
            await message.answer(f"Ошибка при получении данных: {str(e)}")
        await state.set_state(RegionState.waiting_for_obl)

@dp.message(RegionState.waiting_for_obl)
async def process_obl_input(message: types.Message, state: FSMContext):
    obl = message.text.strip()

    await state.update_data(obl=obl)

    with open('data.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    try:
        if 'states' in data:
            for oblast in data['states']:
                if oblast['regionName'] == obl:
                    if 'regionChildIds' in oblast and isinstance(oblast['regionChildIds'], list):
                        if not oblast['regionChildIds']:
                            # Сохраняем пользователя в базе данных, если regionChildIds пуст
                            user_id = message.from_user.id
                            region_name = obl
                            reg_id = oblast['regionId']
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO users (user_id, region_id, reg_id) VALUES (?, ?, ?)", (user_id, region_name, reg_id))
                            conn.commit()
                            conn.close()
                            await message.answer(f"Вы выбрали регион {obl}. Информация сохранена в базе данных.", reply_markup=main_menu())
                            return
                        # Если regionChildIds не пуст, продолжаем обрабатывать дальше
                        regions_text = "\n\n".join(f"<code>{region['regionName']}</code>" for region in oblast['regionChildIds'] if isinstance(region, dict))
                        await message.answer(regions_text, parse_mode="HTML", reply_markup=main_menu())
                        await message.answer("Пожалуйста, введите регион. Нажмите на регион для копирования", reply_markup=main_menu())
                        break
        else:
            await message.answer("Ошибка: Данные о регионах отсутствуют.")
    except Exception as e:
        await message.answer(f"Ошибка при получении данных: {str(e)}")
    await state.set_state(RegionState.waiting_for_regi)


@dp.message(RegionState.waiting_for_regi)
async def process_regi_input(message: types.Message, state: FSMContext):
    rajon = message.text.strip()

    data_state = await state.get_data()
    obl = data_state.get('obl')

    await state.update_data(obl=obl, rajon=rajon)

    with open('data.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    try:
        if 'states' in data:
            for oblast in data['states']:
                if oblast['regionName'] == obl:
                    if 'regionChildIds' in oblast and isinstance(oblast['regionChildIds'], list):
                        for sub in oblast['regionChildIds']:
                            if sub['regionName'] == rajon:
                                if 'regionChildIds' in sub and isinstance(sub['regionChildIds'], list):
                                    if not sub['regionChildIds']:
                                        # Сохраняем пользователя в базе данных, если regionChildIds пуст
                                        user_id = message.from_user.id
                                        region_name = rajon
                                        reg_id = sub['regionId']
                                        conn = get_db_connection()
                                        cursor = conn.cursor()
                                        cursor.execute("INSERT OR REPLACE INTO users (user_id, region_id, reg_id) VALUES (?, ?, ?)", (user_id, region_name, reg_id))
                                        conn.commit()
                                        conn.close()
                                        await message.answer(f"Вы выбрали регион {rajon}. Информация сохранена в базе данных.", reply_markup=main_menu())
                                        return
                                    regions_text = "\n\n".join(f"<code>{city['regionName']}</code>" for city in sub['regionChildIds'] if isinstance(city, dict))
                                    await message.answer(regions_text, parse_mode="HTML", reply_markup=main_menu())
                                    await message.answer("Пожалуйста, введите свой город. Нажмите на город для копирования", reply_markup=main_menu())
                        break
        else:
            await message.answer("Ошибка: Данные о регионах отсутствуют.")
    except Exception as e:
        await message.answer(f"Ошибка при получении данных: {str(e)}")
    await state.set_state(RegionState.waiting_for_city)


@dp.message(RegionState.waiting_for_city)
async def process_city_input(message: types.Message, state: FSMContext):
    citys = message.text.strip()
    data_state = await state.get_data()
    obl = data_state.get('obl')
    rajon = data_state.get('rajon')

    await state.update_data(citys=citys)

    with open('data.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    try:
        if 'states' in data:
            for oblast in data['states']:
                if oblast['regionName'] == obl:
                    if 'regionChildIds' in oblast and isinstance(oblast['regionChildIds'], list):
                        for sub in oblast['regionChildIds']:
                            if sub['regionName'] == rajon:
                                if 'regionChildIds' in sub and isinstance(sub['regionChildIds'], list):
                                    for city in sub['regionChildIds']:
                                        if city['regionName'] == citys:
                                            if 'regionChildIds' not in city or not city['regionChildIds']:
                                                user_id = message.from_user.id
                                                region_name = citys
                                                reg_id = city['regionId']
                                                conn = get_db_connection()
                                                cursor = conn.cursor()
                                                cursor.execute("INSERT OR REPLACE INTO users (user_id, region_id, reg_id) VALUES (?, ?, ?)", (user_id, region_name, reg_id))
                                                conn.commit()
                                                conn.close()
                                                await message.answer(f"Вы выбрали город {citys}. Информация сохранена в базе данных.", reply_markup=main_menu())
                                                await state.clear()
                                                return
                                            await message.answer(f"<code>{city['regionName']}</code>")
                                            break
                                else:
                                    # Если у района нет дочерних регионов, сохраняем район как конечный выбор
                                    user_id = message.from_user.id
                                    region_name = rajon
                                    reg_id = sub['regionId']
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("INSERT OR REPLACE INTO users (user_id, region_id, reg_id) VALUES (?, ?, ?)", (user_id, region_name, reg_id))
                                    conn.commit()
                                    conn.close()
                                    await message.answer(f"У региона {rajon} нет городов. Вы выбрали регион {rajon}. Информация сохранена в базе данных.", reply_markup=main_menu())
                                    await state.clear()  # Очищаем состояние
                                    return
                    break
        else:
            await message.answer("Ошибка: Данные о регионах отсутствуют.")
    except Exception as e:
        await message.answer(f"Ошибка при получении данных: {str(e)}")

@dp.message(lambda message: message.text == "✏️ Изменить регион")
async def change_region(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET region_id = NULL, reg_id = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer("Вы сбросили регион. Пожалуйста, выберите новый регион.", reply_markup=main_menu())
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=header) as response:
                if response.status == 200:
                    data = await response.json()

                    with open("data.json", "w", encoding="utf-8") as file:
                        json.dump(data, file, indent=4, ensure_ascii=False)

                    # Обходим все регионы
                    if 'states' in data:
                        regions_text = "\n\n".join(f"<code>{obl['regionName']}</code>" for obl in data['states'])
                        await message.answer(regions_text, parse_mode="HTML", reply_markup=main_menu())
                        await message.answer("Пожалуйста, введите область. Нажмите на область для копирования", reply_markup=main_menu())
                    else:
                        await message.answer("Ошибка: Данные о регионах отсутствуют.")
                else:
                    await message.answer(f"Ошибка API: {response.status}")
    except Exception as e:
        await message.answer(f"Ошибка при получении данных: {str(e)}")

    # Устанавливаем состояние для ожидания ввода области
    await state.set_state(RegionState.waiting_for_obl)


# --- КНОПКА ПРОВЕРИТЬ СЕЙЧАС ---"
@dp.message(lambda message: message.text == "🔔 Проверить сейчас")
async def check_alert_now(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT reg_id FROM users WHERE user_id = ?", (user_id,))
    reg_id = cursor.fetchone()

    if reg_id:
        reg_id = reg_id[0]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_alert, headers=header) as response:
                if response.status == 200:
                    data = await response.json()

                    with open("data_alert.json", "w", encoding="utf-8") as file:
                        json.dump(data, file, indent=4, ensure_ascii=False)

                    # Обходим все регионы
                    for region in data:
                        if region["regionId"] == str(reg_id):
                            if region["activeAlerts"]:
                                for alert in region["activeAlerts"]:
                                    await message.answer(f"{alert['type']}")
                            else:
                                await message.answer("Нет тревоги")
                            return

                    await message.answer("Нет тревоги")
                else:
                    await message.answer(f"Ошибка API: {response.status}")
    except Exception as e:
        await message.answer(f"Ошибка при получении данных: {str(e)}")

# --- КНОПКА НАЗАД ---"
@dp.message(lambda message: message.text == "🔙 Назад")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()  # Сбрасываем текущее состояние
    await message.answer("Выберите действие:", reply_markup=main_menu())

# --- ЗАПУСК БОТА ---
async def main():
    create_db()
    greate_db_user()
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())