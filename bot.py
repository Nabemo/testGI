import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import json
import httpx

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = 'ВАШ_TELEGRAM_BOT_TOKEN'
FRAGMENT_API_KEY = 'ВАШ_FRAGMENT_API_KEY'
ADMIN_IDS = [ВАШ_TELEGRAM_ID]  # Ваш ID для получения уведомлений

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния для FSM
class UserState(StatesGroup):
    waiting_for_payment = State()

# Данные о товарах (можно вынести в БД)
STAR_PRODUCTS = [
    {"id": 1, "name": "Малая звезда", "price": 10, "fragment_id": "star1", "emoji": "⭐"},
    {"id": 2, "name": "Звезда-гигант", "price": 30, "fragment_id": "star2", "emoji": "🌟"},
    {"id": 3, "name": "Млечный путь", "price": 100, "fragment_id": "star3", "emoji": "🌌"}
]

# Класс для работы с Fragment API
class FragmentAPI:
    def __init__(self, api_key):
        self.base_url = "https://api.fragment.com"
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def get_balance(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/balance", headers=self.headers)
            return response.json().get("balance", 0)

    async def create_invoice(self, fragment_id, price):
        data = {
            "item_id": fragment_id,
            "price": price,
            "currency": "USD"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/invoice", json=data, headers=self.headers)
            return response.json()

fragment_api = FragmentAPI(FRAGMENT_API_KEY)

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🛍️ Магазин звёзд"))
    
    await message.answer(
        "✨ Добро пожаловать в Cosmic Stars Shop!\n"
        "Здесь вы можете купить эксклюзивные звёзды через Fragment.",
        reply_markup=keyboard
    )

    # Отправляем уведомление админу
    if message.from_user.id not in ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                5029778246,
                f"Новый пользователь:\n"
                f"ID: {message.from_user.id}\n"
                f"Username: @{message.from_user.username}"
            )

# Кнопка магазина
@dp.message_handler(text="🛍️ Магазин звёзд")
async def show_shop(message: types.Message):
    # Получаем баланс пользователя
    balance = await fragment_api.get_balance()
    
    # Создаем инлайн-клавиатуру с товарами
    keyboard = types.InlineKeyboardMarkup()
    for product in STAR_PRODUCTS:
        keyboard.add(
            types.InlineKeyboardButton(
                text=f"{product['emoji']} {product['name']} - {product['price']}⭐",
                callback_data=f"buy_{product['id']}"
            )
        )
    
    await message.answer(
        f"🌟 <b>Ваш баланс:</b> {balance}⭐\n"
        "Выберите звезду для покупки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Обработка выбора товара
@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def process_buy(callback_query: types.CallbackQuery, state: FSMContext):
    product_id = int(callback_query.data.split('_')[1])
    product = next(p for p in STAR_PRODUCTS if p["id"] == product_id)
    
    # Сохраняем данные о покупке
    await state.update_data(
        product_id=product["id"],
        product_name=product["name"],
        price=product["price"]
    )
    
    # Создаем счет в Fragment
    invoice = await fragment_api.create_invoice(product["fragment_id"], product["price"])
    
    if invoice.get("status") == "success":
        # Показываем кнопку оплаты
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                text="💳 Оплатить через Fragment",
                url=invoice["payment_url"]
            )
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            f"🛒 Вы выбрали: <b>{product['name']}</b>\n"
            f"💵 Сумма к оплате: <b>{product['price']}⭐</b>\n"
            "Нажмите кнопку ниже для оплаты:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await UserState.waiting_for_payment.set()
    else:
        await bot.send_message(
            callback_query.from_user.id,
            "⚠️ Ошибка при создании счета. Попробуйте позже."
        )

# Проверка оплаты (можно настроить через webhook)
@dp.message_handler(state=UserState.waiting_for_payment)
async def check_payment(message: types.Message, state: FSMContext):
    # Здесь должна быть логика проверки оплаты через Fragment API
    # В демо-версии просто сбрасываем состояние
    
    user_data = await state.get_data()
    await message.answer(
        f"✅ Спасибо за покупку {user_data['product_name']}!\n"
        "Ваша звезда была добавлена в коллекцию."
    )
    
    # Уведомление админу
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"Новая покупка:\n"
            f"Товар: {user_data['product_name']}\n"
            f"Цена: {user_data['price']}⭐\n"
            f"Пользователь: @{message.from_user.username}"
        )
    
    await state.finish()

# Запуск бота
async def on_startup(dp):
    await bot.send_message(ADMIN_IDS[0], "🤖 Бот магазина звёзд запущен!")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)