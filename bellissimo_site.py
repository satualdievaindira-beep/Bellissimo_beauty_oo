#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bellissimo_beauty_kg: сайт салона Bellissimo Beauty Salon (Бишкек).
ВЕСЬ САЙТ В ОДНОМ ФАЙЛЕ: логотип, стили и страницы лежат внутри. Просто запустите его.

Что умеет:
  * показывает услуги и цены из прайс-листа (файл data.py)
  * онлайн-запись: клиент выбирает услугу, дату и время, нажимает кнопку,
    и его перекидывает в WhatsApp администратора с готовым сообщением
  * кнопка "Мы на карте" ведёт на точку салона в 2ГИС

Запуск в PyCharm: откройте файл и нажмите зелёную стрелку (Run).
Браузер откроется сам. Если нет, откройте адрес, который напечатан в консоли.
Нужен только Flask: pip install flask
"""

import base64
import os
import socket
import sys
import threading
import webbrowser
from datetime import date, datetime, timedelta
from urllib.parse import quote

try:
    from flask import Flask, Response, redirect, render_template, request, url_for
    from jinja2 import DictLoader
except ImportError:
    print("Не найден Flask. Откройте вкладку Terminal в PyCharm и выполните: pip install flask")
    sys.exit(1)

# ---------------------------------------------------------------------------
# НАСТРОЙКИ: контакты и ссылки меняются здесь
# ---------------------------------------------------------------------------
SITE_NAME = "Bellissimo_beauty_kg"
SALON_NAME = "Bellissimo Beauty Salon"
CITY = "Бишкек"

# Ссылка на логотип. Если оставить пустой, берётся логотип, встроенный в этот файл
LOGO_URL = ""

# Точка салона в 2ГИС
MAP_URL = "https://2gis.kg/bishkek/geo/15763234351112671"

# WhatsApp администратора: цифры с кодом страны, без плюса и пробелов
WHATSAPP_DIGITS = "996550402057"
WHATSAPP_DISPLAY = "+996 550 402 057"

# Время работы салона: с 10:00 до 19:00 (в минутах от полуночи).
# В форме записи предлагаются времена начала с шагом SLOT_STEP, последняя запись раньше закрытия.
SLOT_START = 10 * 60
SLOT_END = 19 * 60
SLOT_STEP = 30
HOURS_TEXT = f"{SLOT_START // 60:02d}:{SLOT_START % 60:02d}-{SLOT_END // 60:02d}:{SLOT_END % 60:02d}"

BOOK_DAYS_AHEAD = 60  # на сколько дней вперёд можно записаться

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# ---------------------------------------------------------------------------
# ПРАЙС-ЛИСТ
# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "key": "cuts",
        "title": "Стрижки и укладки",
        "text": "Женские, мужские, корейские и детские стрижки, укладки и локоны.",
        "items": [
            ("Женские стрижки", "800 с", ""),
            ("Мужские стрижки", "500 с", ""),
            ("Корейские стрижки", "700 с", ""),
            ("Детские стрижки", "400 с", "до 12 лет"),
            ("Укладка на короткие волосы", "500 с", ""),
            ("Локоны на брашинг", "800-1000 с", ""),
        ],
    },
    {
        "key": "color",
        "title": "Окрашивание и уход за волосами",
        "text": "Окрашивание, осветление маслами, химическая завивка, кератин и полный уход.",
        "items": [
            ("Покраска в один тон", "800 с", "не включая краску"),
            ("Сложное окрашивание", "4000 с", "цена зависит от длины волос"),
            ("Осветление волос маслами", None, ""),
            ("Полный уход за волосами", None, ""),
            ("Химическая завивка", "1500 с", ""),
            ("Кератиновое выпрямление", "4000 с", ""),
        ],
    },
    {
        "key": "brows",
        "title": "Брови",
        "text": "Коррекция формы и окрашивание бровей.",
        "items": [
            ("Окрашивание бровей", None, ""),
            ("Коррекция бровей", None, ""),
        ],
    },
    {
        "key": "nails",
        "title": "Маникюр и педикюр",
        "text": "Гигиенический маникюр и педикюр, гель-лак, наращивание и дизайн.",
        "items": [
            ("Гигиенический маникюр", "500 с", ""),
            ("Маникюр с покрытием гель-лака", "900 с", ""),
            ("Наращивание ногтей", "1400 с", ""),
            ("Снятие покрытия", "200 с", ""),
            ("Втирка", "200 с", ""),
            ("Френч", "200 с", ""),
            ("Дизайн (стразы, рисунки, слайдеры и др.)", "от 200 с", "в зависимости от сложности"),
            ("Гигиенический педикюр", "700 с", ""),
            ("Педикюр с покрытием гель-лака", "1200 с", ""),
        ],
    },
    {
        "key": "laser",
        "title": "Лазерная эпиляция",
        "text": "Безболезненное удаление нежелательных волос на любых зонах.",
        "items": [
            ("Бикини", "1000 с", ""),
            ("Глубокое бикини", "1200 с", ""),
            ("Ягодицы", "700 с", ""),
            ("Живот", "700 с", ""),
            ("Линия живота", "400 с", ""),
            ("Спина", "900 с", ""),
            ("Поясница", "700 с", ""),
            ("Подмышки", "600 с", ""),
            ("Руки до локтей", "800 с", ""),
            ("Руки полностью", "1200 с", ""),
            ("Ноги до колен", "1000 с", ""),
            ("Ноги полностью", "1500 с", ""),
            ("Шея полностью", "550 с", ""),
            ("Лицо (части)", "350 с", ""),
            ("Лицо полностью", "1100 с", ""),
            ("Усики", "300 с", ""),
            ("Подбородок", "350 с", ""),
        ],
    },
]


def all_services():
    """Плоский список услуг. У каждой есть id вида 'cuts-0', по нему работает форма записи."""
    result = []
    for cat in CATEGORIES:
        for index, (name, price, note) in enumerate(cat["items"]):
            result.append({
                "id": f"{cat['key']}-{index}",
                "category": cat["key"],
                "category_title": cat["title"],
                "name": name,
                "price": price,
                "note": note,
            })
    return result


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------
app = Flask(__name__)

SERVICES = all_services()
SERVICES_BY_ID = {s["id"]: s for s in SERVICES}


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def time_options():
    """Список времён для выпадающего списка: '10:00', '10:30', ..."""
    return [f"{m // 60:02d}:{m % 60:02d}" for m in range(SLOT_START, SLOT_END, SLOT_STEP)]


def format_date(d):
    """15 октября, среда"""
    return f"{d.day} {MONTHS[d.month - 1]}, {WEEKDAYS[d.weekday()]}"


def clean(text, limit):
    return " ".join((text or "").split())[:limit]


def build_message(service, day, time_str, name="", comment=""):
    """Текст, который клиент отправит администратору в WhatsApp."""
    price = f" ({service['price']})" if service["price"] else ""
    lines = [
        f"Здравствуйте! Хочу записаться в {SALON_NAME}.",
        f"Услуга: {service['name']}{price}",
        f"Дата: {format_date(day)}",
        f"Время: {time_str}",
    ]
    if name:
        lines.append(f"Имя: {name}")
    if comment:
        lines.append(f"Комментарий: {comment}")
    lines.append("Подтвердите, пожалуйста, запись.")
    return "\n".join(lines)


def whatsapp_link(text=""):
    base = f"https://wa.me/{WHATSAPP_DIGITS}"
    return f"{base}?text={quote(text)}" if text else base


def validate_booking(form):
    """Проверяет форму записи. Возвращает (данные, список ошибок)."""
    errors = []
    service = SERVICES_BY_ID.get(form.get("service", ""))
    if not service:
        errors.append("Выберите услугу.")

    day = None
    try:
        day = date.fromisoformat(form.get("day", ""))
    except ValueError:
        errors.append("Выберите дату.")
    else:
        today = date.today()
        if day < today:
            errors.append("Нельзя записаться на прошедшую дату.")
        elif day > today + timedelta(days=BOOK_DAYS_AHEAD):
            errors.append(f"Запись открыта на {BOOK_DAYS_AHEAD} дней вперёд.")

    time_str = form.get("time", "")
    if time_str not in time_options():
        errors.append("Выберите время.")
    elif day == date.today():
        hour, minute = map(int, time_str.split(":"))
        if datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute) < datetime.now():
            errors.append("Это время уже прошло. Выберите более позднее.")

    return {"service": service, "day": day, "time": time_str}, errors


@app.context_processor
def inject_globals():
    return {
        "site_name": SITE_NAME,
        "salon_name": SALON_NAME,
        "city": CITY,
        "hours_text": HOURS_TEXT,
        "map_url": MAP_URL,
        "logo_url": LOGO_URL or url_for("asset_logo"),
        "wa_display": WHATSAPP_DISPLAY,
        "wa_link": whatsapp_link(f"Здравствуйте! Хочу уточнить по услугам {SALON_NAME}."),
        "tel_link": "tel:+" + WHATSAPP_DIGITS,
    }


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    # form-action намеренно не ограничиваем: после записи форма перекидывает в WhatsApp
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data: https:; "
        "connect-src 'self'; frame-ancestors 'none'"
    )
    return resp


# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------
def render_home(form=None, errors=None, status=200):
    today = date.today()
    form = form or {"service": request.args.get("service", ""), "day": "", "time": "", "name": "", "comment": ""}
    return render_template(
        "index.html",
        categories=CATEGORIES,
        services=SERVICES,
        times=time_options(),
        form=form,
        errors=errors or [],
        min_day=today.isoformat(),
        max_day=(today + timedelta(days=BOOK_DAYS_AHEAD)).isoformat(),
    ), status


@app.route("/")
def index():
    return render_home()


@app.route("/book", methods=["POST"])
def book():
    """Принимает форму записи и перекидывает клиента в WhatsApp с готовым сообщением."""
    form = {
        "service": request.form.get("service", ""),
        "day": request.form.get("day", ""),
        "time": request.form.get("time", ""),
        "name": clean(request.form.get("name"), 60),
        "comment": clean(request.form.get("comment"), 200),
    }
    booking, errors = validate_booking(form)
    if errors:
        return render_home(form, errors, 400)
    message = build_message(booking["service"], booking["day"], booking["time"], form["name"], form["comment"])
    return redirect(whatsapp_link(message), code=303)


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\n", mimetype="text/plain")


@app.errorhandler(404)
def not_found(_err):
    return render_template("error.html", code=404, title="Страница не найдена",
                           text="Такой страницы нет. Вернитесь на главную."), 404


@app.errorhandler(500)
def server_error(_err):
    return render_template("error.html", code=500, title="Ошибка на нашей стороне",
                           text="Попробуйте обновить страницу через минуту."), 500


# ---------------------------------------------------------------------------
# Страницы сайта (шаблоны Jinja2), стили и скрипт. Редактировать можно прямо здесь.
# ---------------------------------------------------------------------------
TEMPLATES = {}
TEMPLATES['base.html'] = r'''<!doctype html>
<html lang="ru" class="no-js">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{% block title %}Салон красоты в Бишкеке{% endblock %} | {{ site_name }}</title>
  <meta name="description" content="{{ salon_name }} в Бишкеке: стрижки, окрашивание, уход за волосами, брови, маникюр, педикюр и лазерная эпиляция. Запись в WhatsApp.">
  <meta name="theme-color" content="#0B1426">
  <meta property="og:title" content="{{ salon_name }}">
  <meta property="og:image" content="{{ logo_url }}">
  <link rel="icon" href="{{ logo_url }}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{{ url_for('asset_css') }}">
</head>
<body>
<a class="skip" href="#main">К содержимому</a>

<header class="site-header">
  <a class="brand" href="{{ url_for('index') }}" aria-label="{{ salon_name }}">
    <img src="{{ logo_url }}" alt="" width="44" height="44">
    <span class="brand-text">Bellissimo<small>Beauty Salon</small></span>
  </a>
  <nav id="nav" class="nav" aria-label="Меню">
    <a href="{{ url_for('index') }}#services">Услуги</a>
    <a href="{{ url_for('index') }}#booking">Запись</a>
    <a href="{{ url_for('index') }}#contacts">Контакты</a>
    <a class="btn small wa" href="{{ wa_link }}" target="_blank" rel="noopener">WhatsApp</a>
  </nav>
  <button class="nav-toggle" aria-expanded="false" aria-controls="nav" aria-label="Открыть меню"><span></span><span></span><span></span></button>
</header>

<main id="main">
  {% block content %}{% endblock %}
</main>

<footer class="site-footer">
  <p><strong>{{ site_name }}</strong> · {{ salon_name }}, {{ city }}</p>
  <p class="muted">Время работы: {{ hours_text }}</p>
  <p class="muted">&copy; {{ salon_name }}</p>
</footer>

<div class="action-bar">
  <a class="ab wa" href="{{ wa_link }}" target="_blank" rel="noopener">WhatsApp</a>
  <a class="ab primary" href="{{ url_for('index') }}#booking">Записаться</a>
</div>
<script src="{{ url_for('asset_js') }}" defer></script>
</body>
</html>
'''

TEMPLATES['index.html'] = r'''{% extends 'base.html' %}
{% block content %}

<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">{{ city }} · салон красоты</p>
    <h1>Красота, в которой вы уверены</h1>
    <p class="lead">Стрижки, окрашивание, уход за волосами, брови, маникюр и лазерная эпиляция. Выберите услугу, дату и время, и мы продолжим в WhatsApp.</p>
    <div class="actions">
      <a class="btn" href="#booking">Записаться</a>
      <a class="btn ghost" href="{{ map_url }}" target="_blank" rel="noopener">Мы на карте 2ГИС</a>
    </div>
    <ul class="tags">
      <li>Стрижки и окрашивание</li>
      <li>Маникюр и педикюр</li>
      <li>Лазерная эпиляция</li>
    </ul>
  </div>
  <div class="hero-banner">
    <div class="glow"></div>
    <img src="{{ logo_url }}" alt="{{ salon_name }}" width="460" height="460">
  </div>
</section>

<section class="section" id="services">
  <div class="section-head">
    <h2>Услуги и цены</h2>
    <p class="lead">Цены в сомах. Выберите направление или смотрите всё сразу.</p>
  </div>
  <nav class="chips" aria-label="Направления">
    <button type="button" class="chip active" data-filter="all">Все</button>
    {% for cat in categories %}<button type="button" class="chip" data-filter="{{ cat.key }}">{{ cat.title }}</button>{% endfor %}
  </nav>

  {% for cat in categories %}
  <section class="price-block" data-cat="{{ cat.key }}">
    <header>
      <span class="num">{{ '%02d' % loop.index }}</span>
      <div><h3>{{ cat.title }}</h3><p class="muted">{{ cat.text }}</p></div>
    </header>
    <ul class="price-list {{ 'two-col' if cat['items'] | length > 8 }}">
      {% set cat_key = cat.key %}
      {% for name, price, note in cat['items'] %}
      <li>
        <div class="item-main">
          <span class="item-name">{{ name }}</span>
          {% if note %}<span class="item-note">{{ note }}</span>{% endif %}
        </div>
        <span class="item-price {{ '' if price else 'ask' }}">{{ price or 'Уточняйте цену' }}</span>
        <a class="pick" href="{{ url_for('index', service=cat_key ~ '-' ~ loop.index0) }}#booking" data-service="{{ cat_key }}-{{ loop.index0 }}" aria-label="Записаться: {{ name }}">Записаться</a>
      </li>
      {% endfor %}
    </ul>
  </section>
  {% endfor %}
</section>

<section class="section booking" id="booking">
  <div class="booking-grid">
    <div>
      <h2>Запись в WhatsApp</h2>
      <ol class="steps">
        <li><strong>Выберите</strong> услугу, дату и удобное время.</li>
        <li><strong>Нажмите</strong> «Записаться в WhatsApp»: откроется чат с администратором.</li>
        <li><strong>Отправьте</strong> готовое сообщение. Администратор подтвердит запись.</li>
      </ol>
      <div class="preview" aria-live="polite">
        <p class="muted">Так будет выглядеть ваше сообщение</p>
        <pre id="preview">Выберите услугу, дату и время.</pre>
      </div>
    </div>

    <form method="post" action="{{ url_for('book') }}" id="booking-form" class="form" data-salon="{{ salon_name }}" novalidate>
      {% if errors %}<div class="errors" role="alert">{% for e in errors %}<p>{{ e }}</p>{% endfor %}</div>{% endif %}
      <label>Услуга
        <select name="service" id="service" required>
          <option value="">Выберите услугу</option>
          {% for cat in categories %}
          <optgroup label="{{ cat.title }}">
            {% for name, price, note in cat['items'] %}
            {% set sid = cat.key ~ '-' ~ loop.index0 %}
            <option value="{{ sid }}" data-name="{{ name }}" data-price="{{ price or '' }}" {{ 'selected' if form.service == sid }}>{{ name }}{% if price %} · {{ price }}{% endif %}</option>
            {% endfor %}
          </optgroup>
          {% endfor %}
        </select>
      </label>
      <div class="row">
        <label>Дата
          <input type="date" name="day" id="day" value="{{ form.day }}" min="{{ min_day }}" max="{{ max_day }}" required>
        </label>
        <label>Время
          <select name="time" id="time" required>
            <option value="">Выберите время</option>
            {% for t in times %}<option value="{{ t }}" {{ 'selected' if form.time == t }}>{{ t }}</option>{% endfor %}
          </select>
        </label>
      </div>
      <label>Ваше имя <span class="muted">(по желанию)</span>
        <input name="name" id="name" value="{{ form.name }}" maxlength="60" autocomplete="name">
      </label>
      <label>Комментарий <span class="muted">(по желанию)</span>
        <textarea name="comment" id="comment" rows="2" maxlength="200" placeholder="Например: хочу светлый оттенок">{{ form.comment }}</textarea>
      </label>
      <button class="btn wa full" type="submit">Записаться в WhatsApp</button>
      <p class="muted small-print">После нажатия откроется WhatsApp с готовым сообщением. Запись считается подтверждённой, когда ответит администратор.</p>
    </form>
  </div>
</section>

<section class="section narrow" id="faq">
  <h2>Частые вопросы</h2>
  <div class="faq">
    <details>
      <summary>Как записаться?</summary>
      <p>Выберите услугу, дату и время в форме выше и нажмите «Записаться в WhatsApp». Откроется чат с администратором и готовым сообщением, останется только отправить его.</p>
    </details>
    <details>
      <summary>Что значит «Уточняйте цену»?</summary>
      <p>Для некоторых услуг цена зависит от длины и состояния волос или от объёма работы. Напишите администратору в WhatsApp, и он назовёт точную стоимость.</p>
    </details>
    <details>
      <summary>Как перенести или отменить запись?</summary>
      <p>Напишите администратору в WhatsApp на номер {{ wa_display }}: укажите имя, дату и время записи.</p>
    </details>
    <details>
      <summary>Выбранное время занято. Что делать?</summary>
      <p>Напишите администратору, он подскажет свободное время. Сообщение из формы запись не фиксирует: её подтверждает администратор.</p>
    </details>
    <details>
      <summary>Во сколько вы работаете?</summary>
      <p>Время работы: {{ hours_text }}. В форме записи доступно время с {{ times[0] }} до {{ times[-1] }}.</p>
    </details>
    <details>
      <summary>Где вы находитесь?</summary>
      <p>Нажмите «Мы на карте 2ГИС» или «Открыть в 2ГИС»: там точка салона и маршрут.</p>
    </details>
  </div>
</section>

<section class="section" id="contacts">
  <h2>Как нас найти</h2>
  <p class="lead">Время работы: <strong>{{ hours_text }}</strong></p>
  <div class="contact-grid">
    <article class="card">
      <h3>Мы на карте</h3>
      <p class="muted">{{ salon_name }}, {{ city }}. Откройте точку в 2ГИС: там маршрут от вас до салона.</p>
      <a class="btn" href="{{ map_url }}" target="_blank" rel="noopener">Открыть в 2ГИС</a>
    </article>
    <article class="card">
      <h3>WhatsApp администратора</h3>
      <p class="phone"><a href="{{ tel_link }}">{{ wa_display }}</a></p>
      <p class="muted">Пишите по любым вопросам: свободное время, стоимость, подготовка к процедуре.</p>
      <a class="btn wa" href="{{ wa_link }}" target="_blank" rel="noopener">Написать в WhatsApp</a>
    </article>
  </div>
</section>
{% endblock %}
'''

TEMPLATES['error.html'] = r'''{% extends 'base.html' %}
{% block title %}{{ title }}{% endblock %}
{% block content %}
<section class="section narrow center">
  <p class="eyebrow">Ошибка {{ code }}</p>
  <h1>{{ title }}</h1>
  <p class="lead">{{ text }}</p>
  <a class="btn" href="{{ url_for('index') }}">На главную</a>
</section>
{% endblock %}
'''


CSS = r'''/* ==========================================================================
   Bellissimo_beauty_kg: тёмно-синий стиль
   Цвета взяты у логотипа: глубокий синий фон, белый засечный шрифт и
   холодный голубой акцент. Зелёный используется только для WhatsApp.
   ========================================================================== */
:root {
  --bg: #0B1426;
  --bg-2: #0F1B33;
  --card: #152445;
  --card-2: #1B2F58;
  --logo: #243759;
  --line: rgba(159, 188, 235, .2);
  --text: #EAF0FB;
  --muted: #9FB0CE;
  --accent: #7FA6EA;
  --ice: #C5D9F8;
  --wa: #128C4A;
  --wa-dark: #0E7039;
  --bad: #FF8A80;
  --serif: 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
  --sans: 'Manrope', 'Segoe UI', system-ui, -apple-system, sans-serif;
  --radius: 16px;
  --header-h: 68px;
}

*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: calc(var(--header-h) + 12px); -webkit-text-size-adjust: 100%; }
body {
  margin: 0; color: var(--text); font: 400 1.0625rem/1.65 var(--sans);
  background: radial-gradient(90% 60% at 80% -10%, #1c3466 0%, var(--bg) 60%) fixed, var(--bg);
  -webkit-font-smoothing: antialiased;
}
img { max-width: 100%; display: block; }
h1, h2, h3 { font-family: var(--serif); font-weight: 600; line-height: 1.08; letter-spacing: -.01em; margin: 0 0 .4em; }
h1 { font-size: clamp(2.7rem, 8vw, 5rem); }
h2 { font-size: clamp(2.1rem, 5vw, 3.2rem); }
h3 { font-size: 1.6rem; }
p { margin: 0 0 1em; }
a { color: inherit; text-decoration-color: var(--accent); text-underline-offset: 4px; }
a:hover { color: var(--ice); }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; border-radius: 6px; }
.muted { color: var(--muted); }
.center { text-align: center; }
.lead { font-size: 1.2rem; max-width: 54ch; color: #d3dff5; }
.eyebrow { color: var(--accent); font-weight: 600; font-size: .95rem; margin-bottom: 1rem; }
.skip { position: absolute; left: -999px; top: 0; }
.skip:focus { left: 1rem; top: 1rem; background: var(--text); color: var(--bg); padding: .6rem 1rem; border-radius: 8px; z-index: 99; }

/* ----- Шапка --------------------------------------------------------------- */
.site-header {
  position: sticky; top: 0; z-index: 30; height: var(--header-h);
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0 clamp(1rem, 4vw, 3rem);
  background: rgba(11, 20, 38, .85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: .7rem; text-decoration: none; }
.brand img { width: 44px; height: 44px; border-radius: 50%; }
.brand-text { font: 600 1.55rem/1 var(--serif); display: grid; }
.brand-text small { font: 500 .62rem var(--sans); letter-spacing: .28em; text-transform: uppercase; color: var(--muted); margin-top: .25rem; }
.nav { display: flex; align-items: center; gap: 1.6rem; }
.nav a { text-decoration: none; font-weight: 500; font-size: .98rem; }
.nav a:not(.btn):hover { color: var(--accent); }
.nav-toggle { display: none; width: 44px; height: 44px; border: 1px solid var(--line); border-radius: 50%; background: var(--card); cursor: pointer; padding: 0; position: relative; }
.nav-toggle span { position: absolute; left: 13px; right: 13px; height: 2px; background: var(--text); border-radius: 2px; transition: transform .2s, opacity .2s; }
.nav-toggle span:nth-child(1) { top: 15px; }
.nav-toggle span:nth-child(2) { top: 21px; }
.nav-toggle span:nth-child(3) { top: 27px; }
.nav-toggle[aria-expanded="true"] span:nth-child(1) { transform: translateY(6px) rotate(45deg); }
.nav-toggle[aria-expanded="true"] span:nth-child(2) { opacity: 0; }
.nav-toggle[aria-expanded="true"] span:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }

/* ----- Кнопки -------------------------------------------------------------- */
.btn {
  display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: .8rem 1.7rem;
  border: 1.5px solid var(--ice); background: var(--ice); color: var(--bg); border-radius: 99px;
  font: 700 1rem var(--sans); text-decoration: none; cursor: pointer;
  transition: background .18s, border-color .18s, color .18s, transform .18s;
}
.btn:hover { background: var(--accent); border-color: var(--accent); color: var(--bg); transform: translateY(-2px); }
.btn:active { transform: none; }
.btn.ghost { background: transparent; color: var(--text); border-color: var(--line); }
.btn.ghost:hover { background: var(--card-2); border-color: var(--accent); color: var(--text); }
.btn.wa { background: var(--wa); border-color: var(--wa); color: #fff; }
.btn.wa:hover { background: var(--wa-dark); border-color: var(--wa-dark); color: #fff; }
.btn.small { min-height: 40px; padding: .45rem 1.1rem; font-size: .92rem; }
.btn.full { width: 100%; }
.actions { display: flex; flex-wrap: wrap; gap: .8rem; margin: 1.6rem 0; }

/* ----- Первый экран с баннером --------------------------------------------- */
.hero {
  display: grid; grid-template-columns: 1.1fr .9fr; gap: clamp(1.5rem, 5vw, 4rem); align-items: center;
  max-width: 1240px; margin: 0 auto; padding: clamp(2.5rem, 7vw, 6rem) clamp(1rem, 4vw, 3rem);
}
.tags { list-style: none; display: flex; flex-wrap: wrap; gap: .6rem; padding: 0; margin: 2rem 0 0; }
.tags li { border: 1px solid var(--line); background: rgba(21, 36, 69, .6); border-radius: 99px; padding: .35rem 1rem; font-size: .92rem; color: var(--ice); }
.hero-banner { position: relative; display: grid; place-items: center; width: min(100%, 460px); aspect-ratio: 1; justify-self: center; }
.hero-banner img { position: relative; width: 86%; height: auto; border-radius: 50%; box-shadow: 0 30px 70px rgba(0, 0, 0, .5), 0 0 0 1px var(--line); }
.glow { position: absolute; inset: -8%; border-radius: 50%; background: radial-gradient(circle, rgba(127, 166, 234, .35), transparent 65%); animation: breathe 6s ease-in-out infinite; }
@keyframes breathe { 50% { transform: scale(1.08); opacity: .75; } }

/* ----- Секции --------------------------------------------------------------- */
.section { max-width: 1240px; margin: 0 auto; padding: clamp(3rem, 7vw, 5.5rem) clamp(1rem, 4vw, 3rem); }
.section.narrow { max-width: 760px; }
.section-head { margin-bottom: 1.6rem; }

.chips { display: flex; gap: .5rem; overflow-x: auto; padding: .4rem 0 1rem; scrollbar-width: none; }
.chips::-webkit-scrollbar { display: none; }
.chip {
  flex: none; cursor: pointer; border: 1px solid var(--line); background: var(--card); color: var(--text);
  border-radius: 99px; padding: .55rem 1.2rem; font: 600 .92rem var(--sans); min-height: 44px; transition: background .15s, color .15s;
}
.chip:hover { border-color: var(--accent); }
.chip.active { background: var(--ice); border-color: var(--ice); color: var(--bg); }

.price-block { margin-top: 1.4rem; padding: clamp(1.2rem, 3vw, 2rem); background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); }
.price-block[hidden] { display: none; }
.price-block header { display: flex; align-items: center; gap: 1.1rem; margin-bottom: 1rem; }
.price-block h3 { margin: 0; }
.price-block header p { margin: 0; font-size: .96rem; }
.num { font: 600 2.8rem/1 var(--serif); color: var(--accent); }
.price-list { list-style: none; margin: 0; padding: 0; }
.price-list.two-col { columns: 2; column-gap: 2.4rem; }
.price-list li {
  display: grid; grid-template-columns: 1fr auto auto; gap: .2rem 1rem; align-items: center;
  padding: .85rem 0; border-bottom: 1px solid var(--line); break-inside: avoid;
}
.item-main { display: grid; }
.item-name { font-weight: 600; }
.item-note { font-size: .86rem; color: var(--muted); }
.item-price { font: 700 1.1rem var(--sans); color: var(--ice); white-space: nowrap; }
.item-price.ask { font-weight: 500; font-size: .92rem; color: var(--muted); }
.pick {
  text-decoration: none; font-weight: 700; font-size: .88rem; color: var(--accent); border: 1px solid var(--line);
  border-radius: 99px; padding: .35rem .9rem; min-height: 36px; display: inline-flex; align-items: center; transition: background .15s, color .15s;
}
.pick:hover { background: var(--accent); border-color: var(--accent); color: var(--bg); }

/* ----- Запись --------------------------------------------------------------- */
.booking { background: var(--bg-2); max-width: none; border-block: 1px solid var(--line); }
.booking-grid { max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1.1fr; gap: clamp(1.5rem, 5vw, 4rem); align-items: start; }
.steps { padding-left: 1.2rem; display: grid; gap: .8rem; margin: 1.4rem 0 2rem; }
.steps li::marker { color: var(--accent); font-weight: 700; }
.preview { border: 1px dashed var(--accent); border-radius: var(--radius); padding: 1.1rem 1.3rem; background: rgba(21, 36, 69, .6); }
.preview p { margin: 0 0 .5rem; font-size: .9rem; }
.preview pre { margin: 0; white-space: pre-wrap; word-break: break-word; font: 400 .98rem/1.55 var(--sans); color: var(--ice); }
.form { display: grid; gap: 1rem; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: clamp(1.2rem, 3vw, 2rem); }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
label { display: grid; gap: .35rem; font-weight: 600; font-size: .96rem; }
label .muted { font-weight: 400; }
input, select, textarea {
  font: inherit; font-weight: 400; width: 100%; min-height: 50px; padding: .8rem 1rem; color: var(--text);
  background: var(--bg); border: 1.5px solid var(--line); border-radius: 12px;
}
input[type="date"] { color-scheme: dark; }
option, optgroup { background: var(--bg); color: var(--text); }
input:focus, select:focus, textarea:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 0 3px rgba(127, 166, 234, .2); }
.errors { border: 1px solid var(--bad); border-left-width: 6px; border-radius: 12px; padding: .8rem 1.1rem; background: rgba(255, 138, 128, .08); }
.errors p { margin: .2rem 0; color: var(--bad); font-weight: 600; }
.small-print { font-size: .86rem; margin: 0; }

/* ----- Частые вопросы ------------------------------------------------------- */
.faq { display: grid; gap: .7rem; margin-top: 1.4rem; }
.faq details { background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.faq summary {
  cursor: pointer; list-style: none; padding: 1rem 1.3rem; min-height: 54px; font-weight: 700;
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
}
.faq summary::-webkit-details-marker { display: none; }
.faq summary::after { content: '+'; font: 400 1.7rem/1 var(--sans); color: var(--accent); transition: transform .2s; }
.faq details[open] summary::after { transform: rotate(45deg); }
.faq details p { margin: 0; padding: 0 1.3rem 1.2rem; color: #d3dff5; }

/* ----- Контакты ------------------------------------------------------------- */
.contact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; margin-top: 1.6rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: clamp(1.3rem, 3vw, 2rem); display: flex; flex-direction: column; align-items: flex-start; gap: .2rem; }
.card h3 { font-size: 1.8rem; }
.card .btn { margin-top: auto; }
.phone { font: 600 2rem var(--serif); margin: .2rem 0 .6rem; }
.phone a { text-decoration: none; }

.site-footer { padding: 2rem clamp(1rem, 4vw, 3rem) 2.4rem; border-top: 1px solid var(--line); text-align: center; background: var(--bg); }
.site-footer p { margin: .2rem 0; }
.action-bar { display: none; }

/* ----- Телефон -------------------------------------------------------------- */
@media (max-width: 900px) {
  :root { --header-h: 62px; }
  body { padding-bottom: calc(78px + env(safe-area-inset-bottom, 0)); }
  .nav-toggle { display: block; }
  .nav {
    display: none; position: absolute; left: 0; right: 0; top: 100%; flex-direction: column; align-items: stretch; gap: 0;
    background: var(--bg); border-bottom: 1px solid var(--line); padding: .4rem clamp(1rem, 4vw, 3rem) 1.2rem;
  }
  .nav.open { display: flex; }
  .nav a { padding: .9rem 0; border-bottom: 1px solid var(--line); font-size: 1.08rem; }
  .nav a.btn { margin-top: 1rem; border-bottom: 0; }
  .hero, .booking-grid, .contact-grid { grid-template-columns: 1fr; }
  .hero { padding-top: 1.6rem; }
  .hero-banner { width: min(80%, 320px); order: -1; }
  .actions .btn { flex: 1 1 100%; }
  .price-list.two-col { columns: 1; }
  .action-bar {
    display: grid; grid-template-columns: 1fr 1.3fr; gap: .5rem; position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;
    padding: .6rem .8rem calc(.6rem + env(safe-area-inset-bottom, 0)); background: rgba(11, 20, 38, .94); backdrop-filter: blur(12px); border-top: 1px solid var(--line);
  }
  .ab { display: grid; place-items: center; min-height: 48px; border-radius: 99px; text-decoration: none; font-weight: 700; border: 1.5px solid var(--line); }
  .ab.wa { background: var(--wa); border-color: var(--wa); color: #fff; }
  .ab.primary { background: var(--ice); border-color: var(--ice); color: var(--bg); }
}
@media (max-width: 560px) {
  .row { grid-template-columns: 1fr; }
  .brand-text { font-size: 1.35rem; }
  .price-list li { grid-template-columns: 1fr auto; }
  .price-list li .pick { grid-column: 1 / -1; justify-content: center; }
  .num { font-size: 2.2rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
'''

JS = r'''/* ==========================================================================
   Bellissimo_beauty_kg: интерактив сайта.
   Без этого файла сайт работает: форма записи отправляется обычным способом
   и перекидывает в WhatsApp, а все услуги видны сразу.
   ========================================================================== */
(function () {
  'use strict';

  var html = document.documentElement;
  html.classList.remove('no-js');
  html.classList.add('js');

  /* ----- Меню на телефоне ------------------------------------------------- */
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('nav');
  function closeMenu() {
    if (!nav || !toggle) return;
    nav.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) closeMenu(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
  }

  /* ----- Фильтр услуг по направлениям ------------------------------------- */
  var chips = document.querySelectorAll('.chip[data-filter]');
  var blocks = document.querySelectorAll('.price-block');
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      var key = chip.getAttribute('data-filter');
      chips.forEach(function (c) { c.classList.toggle('active', c === chip); });
      blocks.forEach(function (b) { b.hidden = key !== 'all' && b.getAttribute('data-cat') !== key; });
    });
  });

  /* ----- Форма записи ------------------------------------------------------ */
  var form = document.getElementById('booking-form');
  if (!form) return;

  var service = document.getElementById('service');
  var day = document.getElementById('day');
  var time = document.getElementById('time');
  var nameInput = document.getElementById('name');
  var comment = document.getElementById('comment');
  var preview = document.getElementById('preview');
  var salon = form.getAttribute('data-salon') || '';

  var MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  var WEEKDAYS = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];

  function formatDate(value) {
    var p = value.split('-');
    if (p.length !== 3) return '';
    var d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    if (isNaN(d.getTime())) return '';
    return d.getDate() + ' ' + MONTHS[d.getMonth()] + ', ' + WEEKDAYS[d.getDay()];
  }

  // Текст сообщения. Формат совпадает с тем, что собирает сервер (app.py, build_message).
  function updatePreview() {
    var opt = service.options[service.selectedIndex];
    if (!service.value && !day.value && !time.value) {
      preview.textContent = 'Выберите услугу, дату и время.';
      return;
    }
    var price = opt && opt.getAttribute('data-price') ? ' (' + opt.getAttribute('data-price') + ')' : '';
    var lines = [
      'Здравствуйте! Хочу записаться в ' + salon + '.',
      'Услуга: ' + (service.value ? opt.getAttribute('data-name') + price : '...'),
      'Дата: ' + (formatDate(day.value) || '...'),
      'Время: ' + (time.value || '...')
    ];
    var n = nameInput.value.trim().replace(/\s+/g, ' ');
    var c = comment.value.trim().replace(/\s+/g, ' ');
    if (n) lines.push('Имя: ' + n);
    if (c) lines.push('Комментарий: ' + c);
    lines.push('Подтвердите, пожалуйста, запись.');
    preview.textContent = lines.join('\n');
  }

  [service, day, time, nameInput, comment].forEach(function (el) {
    el.addEventListener('input', updatePreview);
    el.addEventListener('change', updatePreview);
  });

  // Кнопка "Записаться" у услуги: выбираем услугу и плавно едем к форме
  document.querySelectorAll('.pick[data-service]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      service.value = link.getAttribute('data-service');
      updatePreview();
      var target = document.getElementById('booking');
      var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      window.setTimeout(function () { (day.value ? time : day).focus({ preventScroll: true }); }, 450);
    });
  });

  // Проверка перед отправкой: подсказываем, чего не хватает
  form.addEventListener('submit', function (e) {
    var problem = '';
    if (!service.value) problem = 'Выберите услугу.';
    else if (!day.value) problem = 'Выберите дату.';
    else if (!time.value) problem = 'Выберите время.';
    if (!problem) return;
    e.preventDefault();
    var box = form.querySelector('.errors');
    if (!box) {
      box = document.createElement('div');
      box.className = 'errors';
      box.setAttribute('role', 'alert');
      form.insertBefore(box, form.firstChild);
    }
    box.textContent = '';
    var p = document.createElement('p');
    p.textContent = problem;
    box.appendChild(p);
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  updatePreview();
})();
'''

# Логотип (картинка PNG, закодированная в текст)
LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAeAAAAHgCAMAAABKCk6nAAADAFBMVEUiNVUAAAD7/PwcKkUeNFRMWGlueYkhLUjk6u84RViy"
    "usUZKDx6hpTN1Nu5w8yOmKVZZXYAAFUXJDgbKUPb5OodK0eps7vEy9PS2+MAPT0hMU8AAH+ZpLCkrLcZJTsAVVURGSsdLUo7"
    "OzuDjJkUHC8eME8bKEEAf38bJ0SIkpwBATkAAP9VVVUgLks7SmJCTWNia3kNFRYeLkwhLk5BS1wAOnUgLEkA//8UIzAeME0g"
    "MEwjNmB/f39ncnwaJjwhLDwAVao8PHogME1GUlxcaoIgLEVjboIQHS7///8dMEwkMT49UGVVVaoAfwCEjqEAAKoPFh4cJz0A"
    "KlUAf/8ZHkMAVQAPDycXHzMXF0UAKn8APwAfMDweMEkAM5knEycqKiogKEU/UltVVQB8jaCjr8HX4N3//wAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAABrickBAAABAHRSTlP+AP/+/v///v///////////wMxcP+N////BNIC//9NAxevBP8pz1MCJ/8G"
    "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"
    "RU5ErkJggg=="
)
LOGO_PNG = base64.b64decode(LOGO_B64)

app.jinja_env.loader = DictLoader(TEMPLATES)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


@app.route("/assets/style.css")
def asset_css():
    return Response(CSS, mimetype="text/css", headers={"Cache-Control": "no-cache"})


@app.route("/assets/app.js")
def asset_js():
    return Response(JS, mimetype="application/javascript", headers={"Cache-Control": "no-cache"})


@app.route("/assets/logo.png")
def asset_logo():
    return Response(LOGO_PNG, mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------
def find_free_port(preferred=5000):
    """Берёт порт 5000, а если он занят другой программой, первый свободный следом."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


if __name__ == "__main__":
    port = int(os.environ.get("PORT", find_free_port()))
    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(f" Сайт {SITE_NAME} запущен: {url}")
    print(" Чтобы остановить, нажмите красный квадрат в PyCharm (Stop).")
    print("=" * 60)
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
