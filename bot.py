
import os
import time
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# ===========================================================================
# ⚙️ НАСТРОЙКИ СИСТЕМЫ (БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ДЛЯ БЕЗОПАСНОСТИ)
# ===========================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "NEARUSDT", "SUIUSDT", "LINKUSDT", "AVAXUSDT"]
radar_active = False

# Инициализация ИИ-глаз
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def calculate_rsi(closes, period=14):
    if len(closes) < period: return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def scan_market_data(symbol):
    try:
        res_1h = requests.get(f"https://binance.com{symbol}&interval=1h&limit=100").json()
        closes_1h = [float(c) for c in res_1h]
        current_price = closes_1h[-1]
        ma_1h = sum(closes_1h[-50:]) / 50
        
        res_24h = requests.get(f"https://binance.com{symbol}").json()
        change_24h = float(res_24h['priceChangePercent'])
        
        res_15m = requests.get(f"https://binance.com{symbol}&interval=15m&limit=50").json()
        closes_15m = [float(c) for c in res_15m]
        rsi_15m = calculate_rsi(closes_15m)
        
        return current_price, change_24h, current_price > ma_1h, rsi_15m, ma_1h
    except:
        return None, None, False, 50, None

def check_order_book(symbol, current_price):
    try:
        res_depth = requests.get(f"https://binance.com{symbol}&limit=100").json()
        bids = res_depth['bids']
        volumes = [float(b) * float(b) for b in bids]
        avg_wall = sum(volumes) / len(volumes)
        
        for bid in bids:
            price = float(bid)
            volume_usdt = price * float(bid)
            distance = ((current_price - price) / current_price) * 100
            if 0.5 <= distance <= 2.5 and volume_usdt > (avg_wall * 6):
                return price, volume_usdt
        return None, None
    except:
        return None, None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global radar_active
    if not radar_active:
        radar_active = True
        await update.message.reply_text("🤖 **ИИ-Супервизор запущен бесплатно с ИИ-Зрением!**\nСканирую спот Binance Pro...")
        asyncio.create_task(market_radar_loop(context.application, update.message.chat_id))
    else:
        await update.message.reply_text("🤖 Радар уже работает ищет монеты.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global radar_active
    radar_active = False
    await update.message.reply_text("🛑 Радар на паузе. Капитал в безопасности.")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text in ["старт", "start"]: await start_command(update, context)
    elif text in ["стоп", "stop"]: await stop_command(update, context)

# ===========================================================================
# 📸 МОДУЛЬ ИИ-ЗРЕНИЯ ДЛЯ ТВОИХ СКРИНШОТОВ С IPHONE
# ===========================================================================
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Скриншот получен! Пересылаю ИИ для моментального аудита настроек ордера...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_url = photo_file.file_path
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content=[
                        {
                            "type": "text",
                            "text": (
                                "Ты — жесткий торговый робот-супервизор по спотовой торговле на Binance Pro. "
                                "Изучи присланный скриншот торгового интерфейса. Твоя задача выдать жесткий аудит. "
                                "Проверь следующие параметры:\n"
                                "1. Тип ордера должен быть строго ЛИМИТНЫЙ (Limit).\n"
                                "2. Тумблер МАРЖА должен быть строго ВЫКЛЮЧЕН (серый ползунок).\n"
                                "3. Сумма ордера (Всего USDT) должна быть настроена на весь баланс пользователя (~337 USDT).\n\n"
                                "Если все три правила соблюдены идеально, начни ответ строго со строчки: '**ВХОД РАЗРЕШЕН** 🟢'.\n"
                                "Если есть хоть одна ошибка (например: ордер рыночный, или включена маржа, или сумма не 337), "
                                "начни ответ строго со строчки: '**БЛОКИРОВКА** 🚨' и детально, по-русски, объясни пользователю, какую кнопку нажать и где исправить ошибку."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": photo_url}
                        }
                    ]
                }
            ],
            max_tokens=400
        )
        await update.message.reply_text(response.choices.message.content, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка модуля ИИ-Зрения: {e}\nПроверь баланс ключа OpenAI.")

async def market_radar_loop(app: Application, chat_id: int):
    global radar_active
    while radar_active:
        for symbol in WATCHLIST:
            if not radar_active: break
            price, change_24h, above_ema, rsi_15m, ema_1h = scan_market_data(symbol)
            if price is None: continue
            
            trend_signal = above_ema and (0.0 <= change_24h <= 2.0)
            crash_signal = rsi_15m < 25 or (change_24h < -5.0 and rsi_15m < 30)
            
            if trend_signal or crash_signal:
                wall_price, wall_volume = check_order_book(symbol, price)
                if wall_price:
                    buy_limit = wall_price + (wall_price * 0.0003)
                    sell_limit = buy_limit * 1.021
                    type_msg = "🚨 ОБНАРУЖЕН ОТКУП ПРОСАДКИ" if crash_signal else "🎯 НАЙДЕНА ТОЧКА ВХОДА (ТРЕНД)"
                    
                    alert = (
                        f"*{type_msg}*\n\n"
                        f"📦 *Монета:* `{symbol}`\n"
                        f"📊 *Изменение за 24ч:* `{change_24h:.2f}%`\n"
                        f"📈 *1Ч График:* {'НАД ЕМА' if above_ema else 'ПОД ЕМА'}\n"
                        f"🧱 *Стакан:* Плита `${wall_volume:,.0f}` на цене `{wall_price}`\n\n"
                        f"🛠 *ВХОД НА ВСЕ ДЕНЬГИ (337.05 USDT):*\n"
                        f"1️⃣ Ордер: *Лимитный (Buy Limit)*\n"
                        f"2️⃣ Цена покупки: *{buy_limit:.4f}*\n"
                        f"3️⃣ Цель для рыночной продажи (+2%): *{sell_limit:.4f}*\n\n"
                        f"📸 _Выстави ордер на Binance, сделай скриншот экрана телефона и пришли его мне на проверку!_"
                    )
                    await app.bot.send_message(chat_id=chat_id, text=alert, parse_mode="Markdown")
                    await asyncio.sleep(450)
        await asyncio.sleep(20)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    app.run_polling()

if __name__ == "__main__":
    main()
