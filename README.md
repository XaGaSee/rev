# 🤖 OpenRouter Telegram Bot

Production-ready асинхронный Telegram-бот на **aiogram 3** с интеграцией **OpenRouter API**:
диалоги с контекстом, vision (анализ изображений), расшифровка голосовых, генерация картинок,
каталог моделей, профиль/статистика и админ-панель.

## ✨ Возможности

- 💬 Текстовые диалоги с сохранением контекста и стримингом ответа
- 👁️ Анализ изображений (vision) через поддерживающие модели
- 🎙️ Расшифровка голосовых сообщений (OpenAI-совместимый STT-эндпоинт)
- 🎨 Генерация изображений моделями с `modalities=["image"]`
- ⚙️ Каталог моделей по категориям с пагинацией `⬅️ ➡️`
- 🌡️ Настройка температуры и системного промпта
- 🧹 Сброс контекста и подсчёт расхода токенов
- 👤 Профиль и статистика
- 🪙 Учёт стоимости запросов: цена по прайсу OpenRouter, лимит бюджета на пользователя
- 🛡️ Админ-панель: статистика и рассылка
- ⏳ Анти-спам throttling и корректная обработка ошибок OpenRouter (401/429/5xx/сеть)

## 🗂️ Структура проекта

```
ddm1/
├── bot/
│   ├── config.py              # Настройки из .env (pydantic-settings)
│   ├── states.py              # FSM-состояния
│   ├── catalog.py             # Каталог моделей и категорий
│   ├── database/
│   │   ├── db.py              # Асинхронный слой SQLite (aiosqlite)
│   │   └── models.py          # Типизированные записи (User, Stats, ...)
│   ├── handlers/
│   │   ├── commands.py        # /start /help /menu /profile /reset
│   │   ├── text.py            # Текстовые сообщения и генерация картинок
│   │   ├── media.py           # Фото (vision) и голосовые (STT)
│   │   ├── callbacks.py       # Inline-навигация и FSM настроек
│   │   ├── admin.py           # Админ-панель и рассылка
│   │   └── common.py          # Общая логика генерации и стриминга
│   ├── keyboards/
│   │   └── inline.py          # Inline-клавиатуры
│   ├── middlewares/
│   │   ├── throttling.py      # Анти-спам
│   │   ├── locking.py         # Защита от параллельных генераций
│   │   └── user.py            # Регистрация и инъекция пользователя
│   ├── services/
│   │   ├── openrouter.py      # Клиент OpenRouter (стриминг, vision, image gen)
│   │   ├── pricing.py         # Учёт стоимости и бюджета
│   │   ├── audio.py           # Хелперы для голосовых
│   │   ├── image.py           # base64 data-URL хелперы
│   │   └── tokens.py          # Оценка токенов
│   └── utils/
│       └── text.py            # HTML-escape, markdown→HTML, разбивка сообщений
├── main.py                    # Точка входа
├── requirements.txt
└── .env.example
```

## 🚀 Установка

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows (or: cp .env.example .env)
# заполните BOT_TOKEN и OPENROUTER_API_KEY
python main.py
```

## ⚙️ Переменные окружения

Все настройки берутся строго из `.env` (см. `.env.example`). Ключевые:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота от @BotFather |
| `OPENROUTER_API_KEY` | API-ключ OpenRouter |
| `TRANSCRIPTION_*` | STT-эндпоинт для голосовых (OpenAI/Groq) |
| `ADMIN_IDS_RAW` | Список ID админов через запятую |
| `DEFAULT_MODEL` | Модель по умолчанию |
| `MAX_HISTORY_MESSAGES` | Глубина контекста |

## 🧩 Замечания

- Генерация изображений выполняется через чат-эндпоинт OpenRouter с параметром
  `modalities: ["image", "text"]` (например, `google/gemini-2.5-flash-image-preview`).
- Для голосовых можно использовать отдельный STT-сервис (OpenAI `whisper-1` или
  Groq `whisper-large-v3`), указав `TRANSCRIPTION_BASE_URL` и `TRANSCRIPTION_API_KEY`.

## 🛡️ Устойчивость (production hardening)

- **Flood control / 429**: правки превью и отправка сообщений обёрнуты в
  `TelegramRetryAfter` с паузой `await asyncio.sleep(e.retry_after)`.
- **`message is not modified`**: превью сравнивается с предыдущим и не отправляется
  повторно, а ошибка «not modified» глушится; при ошибке парсинга — фолбэк на plain text.
- **Безопасная нарезка HTML**: ответ конвертируется в HTML целиком и режется
  `split_html()`, который закрывает и заново открывает теги на границе чанка —
  незакрытых `<pre>`/`<code>` не бывает.
- **Параллельные запросы**: `ConcurrencyMiddleware` + `ConcurrencyGuard` не дают запустить
  вторую генерацию, пока не завершена первая (команды `/...` не блокируются).
- **Скользящее окно контекста**: `MAX_HISTORY_MESSAGES` последних реплик +
  `MAX_CONTEXT_TOKENS` бюджет токенов (`fit_messages`), системный промпт всегда сохраняется.
- **Голосовые**: лимит 20 МБ, корректное имя `*.ogg` и mime `audio/ogg` при отправке в STT.

## 🪙 Учёт стоимости запросов

- Цены моделей тянутся из `/models` OpenRouter и кэшируются в таблице `pricing`
  (per-token prompt/completion + per-image).
- Реальная стоимость из `usage.cost` (если провайдер её вернул) имеет приоритет над
  расчётом `токены × цена`.
- Накопленный расход и **бюджет** хранятся в БД (`users.cost`, `users.budget`),
  новых переменных окружения **не требуется** — бюджет задаётся в UI:
  `🧠 Настройки → 🪙 Стоимость и бюджет`.
- При достижении лимита генерация блокируется (бюджет `0` = без лимита).
- Профиль и админ-статистика показывают потраченную сумму; для админов есть
  `/pricing` — принудительное обновление прайс-листа.
