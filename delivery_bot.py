import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Запускаем Flask в отдельном потоке
Thread(target=run_flask).start()
"""
Telegram-бот для расчёта стоимости доставки — PackPoint СПб
Стек: Python 3.10+, aiogram 3.x
Установка: pip install aiogram
Запуск: py "delivery bot.py"
"""

import asyncio
import logging
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8969496219:AAHQnLwzz6IwMI2DZP9DmHs5qdBRr8yVIXU"
MANAGER_CHAT_IDS = [898299896, 5228371720]

WAREHOUSE_ADDRESS = "Санкт-Петербург, ул. Профессора Качалова 8И"
MANAGER_CONTACT = "📞 +7 966 860 08 11 (Никита)"

# ─── Навигационные кнопки (всегда видны) ─────────────────────────────────────
NAV_BACK    = "◀️ Назад"
NAV_RESTART = "🔄 Начать заново"
NAV_CANCEL  = "❌ Отмена"
NAV_NEW     = "🔄 Новый расчёт"

# ─── Дни недели ───────────────────────────────────────────────────────────────
DAY_MAP   = {"ПН": 0, "ВТ": 1, "СР": 2, "ЧТ": 3, "ПТ": 4, "СБ": 5, "ВС": 6}
DAY_NAMES = {0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
             4: "Пятница", 5: "Суббота", 6: "Воскресенье"}
MONTH_NAMES = {1:"янв",2:"фев",3:"мар",4:"апр",5:"май",6:"июн",
               7:"июл",8:"авг",9:"сен",10:"окт",11:"ноя",12:"дек"}

# ─── График отгрузок ──────────────────────────────────────────────────────────
SCHEDULE_WB = {
    "Коледино / Обухово / Подольск / Пушкино / Электросталь / Ярославль": [
        ([6], ["СР", "ЧТ", "ПТ"]),
        ([3], ["СБ", "ВТ"]),
    ],
    "Алексин": [([6], ["СР", "ЧТ", "ПТ"]), ([3], ["СБ", "ВТ"])],
    "Никольское": [([6], ["СР"]), ([3], ["СБ"])],
    "Казань / Нижний Новгород": [([6], ["СР", "ЧТ", "ПТ"]), ([3], ["СБ", "ВС", "ВТ"])],
    "Краснодар / Воронеж / Ростов-на-Дону": [([3], ["ВТ", "ЧТ"])],
    "Невинномысск": [([3], ["ВТ", "ЧТ"])],
    "Рязань": [([6], ["СР", "ЧТ", "ПТ"]), ([3], ["СБ", "ВТ"])],
    "Котовск": [([6], ["СР", "ЧТ", "ПТ"]), ([3], ["ВТ"])],
    "Пенза": [([6], ["ЧТ"])],
    "Владимир": [([6], ["СР", "ЧТ", "ПТ"]), ([3], ["СБ", "ВТ"])],
}

SCHEDULE_OZON = {
    "Гривно / Жуковский / Ногинск / Петровское / Пушкино / Ярославль": [
        ([6], ["СР", "ЧТ", "ПТ"]), ([3], ["СБ", "ВТ"])
    ],
    "Домодедово": [([6], ["ЧТ"]), ([3], ["СБ"])],
    "Казань / Нижний Новгород": [([6], ["ЧТ"]), ([3], ["СБ", "ВТ"])],
    "Ростов-на-Дону / Краснодар / Воронеж / Адыгейск": [([3], ["ПН", "ЧТ"])],
    "Невинномысск": [([3], ["ПН", "ВТ"])],
    "Екатеринбург": [([3], ["ПН", "ВТ", "ЧТ"])],
    "Новосибирск": [([6], ["СР"])],
    "Самара": [([6], ["СБ"]), ([3], ["СР"])],
    "Омск": [([3], ["СР", "СБ"])],
    "Уфа": [([6], ["ПТ"])],
}

# ─── Прайс ────────────────────────────────────────────────────────────────────
PALLET_PRICES_WB = {
    "Коледино / Обухово / Подольск / Пушкино / Электросталь / Ярославль": 4704,
    "Алексин": 6300, "Никольское": 6300,
    "Казань / Нижний Новгород": 9450,
    "Краснодар / Воронеж / Ростов-на-Дону": 11792,
    "Невинномысск": 12600, "Рязань": 6300,
    "Котовск": 10238, "Пенза": 10238, "Владимир": 6720,
}
PALLET_PRICES_OZON = {
    "Гривно / Жуковский / Ногинск / Петровское / Пушкино / Ярославль": 4704,
    "Домодедово": 4704, "Казань / Нижний Новгород": 9450,
    "Ростов-на-Дону / Краснодар / Воронеж / Адыгейск": 11760,
    "Невинномысск": 12600, "Екатеринбург": 12600,
    "Новосибирск": 20475, "Самара": 11025, "Омск": 18113, "Уфа": 11813,
}
BOX_PRICES_WB = {
    "Коледино / Обухово / Подольск / Пушкино / Электросталь / Ярославль": 473,
    "Алексин": 630, "Никольское": 630,
    "Казань / Нижний Новгород": 945,
    "Краснодар / Воронеж / Ростов-на-Дону": 1176,
    "Невинномысск": 1260, "Рязань": 630,
    "Котовск": 1019, "Пенза": 1019, "Владимир": 672,
}
BOX_PRICES_OZON = {
    "Гривно / Жуковский / Ногинск / Петровское / Пушкино / Ярославль": 473,
    "Домодедово": 473, "Казань / Нижний Новгород": 945,
    "Ростов-на-Дону / Краснодар / Воронеж / Адыгейск": 1155,
    "Невинномысск": 1260, "Екатеринбург": 1260,
    "Новосибирск": 2363, "Самара": 1103, "Омск": 2100, "Уфа": 1176,
}

# ─── Вспомогательные функции ──────────────────────────────────────────────────
def fmt_date(d: date) -> str:
    return f"{d.day} {MONTH_NAMES[d.month]} ({DAY_NAMES[d.weekday()]})"

def get_upcoming_slots(schedule: list, count: int = 4) -> list:
    today = date.today()
    candidates = []
    for podvoz_days, delivery_days_strs in schedule:
        delivery_days = [DAY_MAP[d] for d in delivery_days_strs]
        for delta in range(1, 61):
            podvoz_date = today + timedelta(days=delta)
            if podvoz_date.weekday() in podvoz_days:
                for dd_delta in range(1, 14):
                    delivery_date = podvoz_date + timedelta(days=dd_delta)
                    if delivery_date.weekday() in delivery_days:
                        candidates.append((podvoz_date, delivery_date))
                        break
    seen = set()
    unique = []
    for item in sorted(candidates, key=lambda x: x[1]):
        key = item[1]
        if key not in seen:
            seen.add(key)
            unique.append(item)
        if len(unique) >= count:
            break
    return unique

def nav_row():
    """Нижняя строка навигации — всегда присутствует в клавиатурах."""
    return [KeyboardButton(text=NAV_BACK),
            KeyboardButton(text=NAV_RESTART),
            KeyboardButton(text=NAV_CANCEL)]

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
def marketplace_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Wildberries")],
            [KeyboardButton(text="🟠 Ozon")],
            [KeyboardButton(text=NAV_CANCEL)],
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def cargo_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🪵 Паллет")],
            [KeyboardButton(text="📦 Коробка")],
            nav_row(),
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def destination_keyboard(destinations: list):
    rows = [[KeyboardButton(text=d)] for d in destinations]
    rows.append(nav_row())
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)

def quantity_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[nav_row()],
        resize_keyboard=True
    )

def dates_keyboard(slots: list):
    buttons = []
    for podvoz, delivery in slots:
        label = f"🚛 {fmt_date(delivery)}  |  📥 к нам {fmt_date(podvoz)}"
        buttons.append([KeyboardButton(text=label)])
    buttons.append(nav_row())
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Оформить заявку")],
            nav_row(),
        ],
        resize_keyboard=True
    )

def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[nav_row()],
        resize_keyboard=True
    )

def restart_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=NAV_NEW)]],
        resize_keyboard=True
    )

# ─── FSM состояния ────────────────────────────────────────────────────────────
class DeliveryForm(StatesGroup):
    marketplace = State()
    cargo_type  = State()
    destination = State()
    quantity    = State()
    choose_date = State()
    confirm     = State()
    name        = State()
    phone       = State()

# ─── Инициализация ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ─── Универсальный обработчик навигации ───────────────────────────────────────
async def handle_nav(message: Message, state: FSMContext) -> bool:
    """Возвращает True если нажата навигационная кнопка и действие выполнено."""
    text = message.text
    current = await state.get_state()

    # Отмена — всегда
    if text == NAV_CANCEL:
        await state.clear()
        await message.answer("Отменено. Нажмите кнопку чтобы начать заново.", reply_markup=restart_keyboard())
        return True

    # Начать заново — всегда
    if text in (NAV_RESTART, NAV_NEW):
        await state.clear()
        await message.answer(
            "👋 Выберите маркетплейс:",
            reply_markup=marketplace_keyboard()
        )
        await state.set_state(DeliveryForm.marketplace)
        return True

    # Назад — зависит от текущего шага
    if text == NAV_BACK:
        state_map = {
            DeliveryForm.cargo_type:  _back_to_marketplace,
            DeliveryForm.destination: _back_to_cargo_type,
            DeliveryForm.quantity:    _back_to_destination,
            DeliveryForm.choose_date: _back_to_quantity,
            DeliveryForm.confirm:     _back_to_choose_date,
            DeliveryForm.name:        _back_to_confirm,
            DeliveryForm.phone:       _back_to_name,
        }
        handler = state_map.get(current)
        if handler:
            await handler(message, state)
        return True

    return False

# ─── Хэндлеры "Назад" ─────────────────────────────────────────────────────────
async def _back_to_marketplace(message, state):
    await state.set_state(DeliveryForm.marketplace)
    await message.answer("Выберите маркетплейс:", reply_markup=marketplace_keyboard())

async def _back_to_cargo_type(message, state):
    await state.set_state(DeliveryForm.cargo_type)
    await message.answer("Выберите тип груза:", reply_markup=cargo_type_keyboard())

async def _back_to_destination(message, state):
    data = await state.get_data()
    prices = data.get("prices", {})
    await state.set_state(DeliveryForm.destination)
    await message.answer("Выберите склад назначения:", reply_markup=destination_keyboard(list(prices.keys())))

async def _back_to_quantity(message, state):
    data = await state.get_data()
    unit = "паллет" if data.get("cargo_type") == "паллет" else "коробок"
    await state.set_state(DeliveryForm.quantity)
    await message.answer(f"Введите количество {unit} (штук):", reply_markup=quantity_keyboard())

async def _back_to_choose_date(message, state):
    data = await state.get_data()
    slots_raw = data.get("slots", [])
    slots = [(date.fromisoformat(p), date.fromisoformat(d)) for p, d in slots_raw]
    await state.set_state(DeliveryForm.choose_date)
    await message.answer("Выберите дату доставки:", reply_markup=dates_keyboard(slots))

async def _back_to_confirm(message, state):
    data = await state.get_data()
    podvoz = date.fromisoformat(data["podvoz_date"])
    delivery = date.fromisoformat(data["delivery_date"])
    await state.set_state(DeliveryForm.confirm)
    await message.answer(
        f"📥 Привезите груз к нам: <b>{fmt_date(podvoz)}</b>\n"
        f"🚛 Доставка на склад МП: <b>{fmt_date(delivery)}</b>\n\n"
        "Что хотите сделать?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard()
    )

async def _back_to_name(message, state):
    await state.set_state(DeliveryForm.name)
    await message.answer("Введите ваше имя:", reply_markup=contact_keyboard())

# ─── Основные хэндлеры ────────────────────────────────────────────────────────
@dp.message(CommandStart())
@dp.message(F.text == NAV_NEW)
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в сервис расчёта доставки!\n\n"
        f"📍 Наш склад: {WAREHOUSE_ADDRESS}\n"
        f"{MANAGER_CONTACT}\n\n"
        "Выберите маркетплейс:",
        reply_markup=marketplace_keyboard()
    )
    await state.set_state(DeliveryForm.marketplace)


@dp.message(DeliveryForm.marketplace)
async def get_marketplace(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    text = message.text
    if "Wildberries" in text:
        mp = "WB"
    elif "Ozon" in text:
        mp = "OZON"
    else:
        await message.answer("⚠️ Выберите маркетплейс из кнопок:", reply_markup=marketplace_keyboard())
        return
    await state.update_data(marketplace=mp)
    await message.answer("Выберите тип груза:", reply_markup=cargo_type_keyboard())
    await state.set_state(DeliveryForm.cargo_type)


@dp.message(DeliveryForm.cargo_type)
async def get_cargo_type(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    text = message.text.lower()
    if "паллет" in text:
        cargo = "паллет"
    elif "коробка" in text or "коробок" in text:
        cargo = "коробка"
    else:
        await message.answer("⚠️ Выберите тип груза из кнопок:", reply_markup=cargo_type_keyboard())
        return
    await state.update_data(cargo_type=cargo)
    data = await state.get_data()
    mp = data["marketplace"]
    if mp == "WB":
        prices = PALLET_PRICES_WB if cargo == "паллет" else BOX_PRICES_WB
    else:
        prices = PALLET_PRICES_OZON if cargo == "паллет" else BOX_PRICES_OZON
    await state.update_data(prices=prices)
    await message.answer(f"Выберите склад назначения ({mp}):", reply_markup=destination_keyboard(list(prices.keys())))
    await state.set_state(DeliveryForm.destination)


@dp.message(DeliveryForm.destination)
async def get_destination(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    data = await state.get_data()
    prices = data["prices"]
    destination = message.text
    if destination not in prices:
        await message.answer("⚠️ Выберите склад из списка:", reply_markup=destination_keyboard(list(prices.keys())))
        return
    await state.update_data(destination=destination)
    unit = "паллет" if data["cargo_type"] == "паллет" else "коробок"
    await message.answer(f"✅ Склад: {destination}\n\nВведите количество {unit} (штук):", reply_markup=quantity_keyboard())
    await state.set_state(DeliveryForm.quantity)


@dp.message(DeliveryForm.quantity)
async def get_quantity(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    try:
        quantity = int(message.text.strip())
        if quantity <= 0: raise ValueError
        if quantity > 14:
            await message.answer(
                "⚠️ Для количества свыше 14 мест стоимость рассчитывается индивидуально.\n"
                f"{MANAGER_CONTACT}",
                reply_markup=restart_keyboard()
            )
            return
    except ValueError:
        await message.answer("⚠️ Введите целое число от 1 до 14:", reply_markup=quantity_keyboard())
        return

    data = await state.get_data()
    price_per_unit = data["prices"][data["destination"]]
    total = price_per_unit * quantity
    await state.update_data(quantity=quantity, price_per_unit=price_per_unit, total=total)

    mp = data["marketplace"]
    schedule_dict = SCHEDULE_WB if mp == "WB" else SCHEDULE_OZON
    slots = get_upcoming_slots(schedule_dict.get(data["destination"], []), count=4)

    if not slots:
        await message.answer(
            "⚠️ Расписание уточняйте у менеджера.\n" + MANAGER_CONTACT,
            reply_markup=restart_keyboard()
        )
        return

    await state.update_data(slots=[(str(p), str(d)) for p, d in slots])
    unit = "паллет" if data["cargo_type"] == "паллет" else "коробка"
    await message.answer(
        f"🧮 <b>Расчёт стоимости доставки</b>\n\n"
        f"🏪 Маркетплейс: {mp}\n"
        f"📦 Тип груза: {data['cargo_type'].capitalize()}\n"
        f"📍 Склад: {data['destination']}\n"
        f"🔢 Количество: {quantity} шт.\n"
        f"💰 Цена за 1 {unit} (с НДС 5%): {price_per_unit:,} руб.\n"
        f"<b>💵 Итого: {total:,} руб.</b>\n\n"
        "📅 Выберите удобную дату доставки на склад МП.\n"
        "Формат: <b>🚛 дата на склад МП | 📥 привезите к нам</b>",
        parse_mode="HTML",
        reply_markup=dates_keyboard(slots)
    )
    await state.set_state(DeliveryForm.choose_date)


@dp.message(DeliveryForm.choose_date)
async def get_date(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    data = await state.get_data()
    slots = [(date.fromisoformat(p), date.fromisoformat(d)) for p, d in data["slots"]]
    chosen = None
    for podvoz, delivery in slots:
        if message.text == f"🚛 {fmt_date(delivery)}  |  📥 к нам {fmt_date(podvoz)}":
            chosen = (podvoz, delivery)
            break
    if not chosen:
        await message.answer("⚠️ Выберите дату из кнопок:", reply_markup=dates_keyboard(slots))
        return
    await state.update_data(podvoz_date=str(chosen[0]), delivery_date=str(chosen[1]))
    await message.answer(
        f"✅ <b>Дата выбрана!</b>\n\n"
        f"📥 Привезите груз к нам: <b>{fmt_date(chosen[0])}</b>\n"
        f"🚛 Доставка на склад МП: <b>{fmt_date(chosen[1])}</b>\n\n"
        "Что хотите сделать?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard()
    )
    await state.set_state(DeliveryForm.confirm)


@dp.message(DeliveryForm.confirm)
async def handle_confirm(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    if message.text == "✅ Оформить заявку":
        await message.answer("Введите ваше имя:", reply_markup=contact_keyboard())
        await state.set_state(DeliveryForm.name)
    else:
        await message.answer("⚠️ Используйте кнопки ниже.", reply_markup=confirm_keyboard())


@dp.message(DeliveryForm.name)
async def get_name(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    await state.update_data(client_name=message.text)
    await message.answer("Введите ваш номер телефона:", reply_markup=contact_keyboard())
    await state.set_state(DeliveryForm.phone)


@dp.message(DeliveryForm.phone)
async def get_phone(message: Message, state: FSMContext):
    if await handle_nav(message, state): return
    await state.update_data(phone=message.text)
    data = await state.get_data()
    podvoz   = date.fromisoformat(data["podvoz_date"])
    delivery = date.fromisoformat(data["delivery_date"])

    # Подтверждение клиенту
    await message.answer(
        f"✅ <b>Заявка оформлена!</b>\n\n"
        f"Менеджер свяжется с вами в ближайшее время.\n\n"
        f"📋 <b>Детали заявки:</b>\n"
        f"👤 {data['client_name']}\n"
        f"📞 {data['phone']}\n"
        f"🏪 {data['marketplace']}\n"
        f"📦 {data['cargo_type'].capitalize()}, {data['quantity']} шт.\n"
        f"📍 Склад МП: {data['destination']}\n"
        f"📥 Привезите к нам: <b>{fmt_date(podvoz)}</b>\n"
        f"🚛 Доставка на склад МП: <b>{fmt_date(delivery)}</b>\n"
        f"<b>💵 Итого: {data['total']:,} руб.</b>\n\n"
        f"📦 <b>Куда везти груз:</b>\n"
        f"📍 {WAREHOUSE_ADDRESS}\n"
        f"{MANAGER_CONTACT}",
        parse_mode="HTML",
        reply_markup=restart_keyboard()
    )

    # Уведомление менеджеру
    await bot.send_message(
        MANAGER_CHAT_ID,
        f"🔔 <b>Новая заявка на доставку!</b>\n\n"
        f"👤 Клиент: {data['client_name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🆔 Telegram ID: {message.from_user.id}\n\n"
        f"🏪 Маркетплейс: {data['marketplace']}\n"
        f"📦 Тип груза: {data['cargo_type'].capitalize()}\n"
        f"🔢 Количество: {data['quantity']} шт.\n"
        f"📍 Склад МП: {data['destination']}\n"
        f"📥 Подвоз к нам: <b>{fmt_date(podvoz)}</b>\n"
        f"🚛 Доставка на МП: <b>{fmt_date(delivery)}</b>\n"
        f"💰 Цена за 1 ед.: {data['price_per_unit']:,} руб.\n\n"
        f"<b>💵 Итого: {data['total']:,} руб.</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ─── Запуск ───────────────────────────────────────────────────────────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
