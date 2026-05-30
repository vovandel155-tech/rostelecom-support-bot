import os
import sqlite3
import csv
import re
import streamlit as st

# Пути
BASE_DIR = os.path.dirname(__file__)
DB_PATH  = os.path.join(BASE_DIR, 'data', 'db.sqlite')
CSV_PATH = os.path.join(BASE_DIR, 'faq.csv')
ESC_PATH = os.path.join(BASE_DIR, 'logs', 'escalations.log')

# Параметры
CLARIFY_THRESHOLD = 1   # минимальное число совпадений
MAX_OPTIONS       = 3   # сколько вариантов подсказать
REQ_PATH = os.path.join(BASE_DIR, 'logs', 'requests.log')

def _log_request(text):
    os.makedirs(os.path.dirname(REQ_PATH), exist_ok=True)
    with open(REQ_PATH, 'a', encoding='utf-8') as f:
        f.write(text + '\n')

# --- Логика эскалации ---
def _log_escalation(text):
    os.makedirs(os.path.dirname(ESC_PATH), exist_ok=True)
    with open(ESC_PATH, 'a', encoding='utf-8') as f:
        f.write(text + '\n')
    st.session_state.operator_online = True

# --- Простое извлечение слов без NLTK ---
def extract_keywords(text):
    return re.findall(r'\b[А-Яа-яA-Za-z0-9Ёё]+\b', text.lower())

# --- Инициализация БД и импорт CSV ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY,
        category TEXT,
        question TEXT,
        answer TEXT
      );
    """)
    conn.commit()
    c.execute("SELECT COUNT(*) FROM faq")
    if c.fetchone()[0] == 0:
        with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f); next(reader)
            for id,cat,q,a in reader:
                c.execute("INSERT OR REPLACE INTO faq VALUES (?,?,?,?)",
                          (id,cat,q,a))
        conn.commit()
    conn.close()

# --- Определение intent с уточнениями ---
def find_intent(text):
    kws = extract_keywords(text)
    if not kws:
        return {"type":"clarify","options":[], "text":None}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT question, answer FROM faq")
    rows = c.fetchall()
    conn.close()

    scored = []
    for question, answer in rows:
        ql = question.lower()
        score = sum(1 for kw in kws if kw in ql)
        if score > 0:
            scored.append((score, question, answer))
    if not scored:
        return {"type":"clarify","options":[], "text":None}

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_q, best_a = scored[0]
    if best_score < CLARIFY_THRESHOLD:
        options = [q for _,q,_ in scored[:MAX_OPTIONS]]
        return {"type":"clarify","options":options, "text":None}

    return {"type":"answer","options":[], "text":best_a}

# --- Обработка отправки сообщения ---
def send_message(text):
    text = text.strip()
    if not text:
        return
    _log_request(text)
    st.session_state.history.append(('Вы', text))
    intent = find_intent(text)

    if intent["type"] == "answer":
        with st.spinner('Бот печатает…'):
            st.session_state.history.append(('Бот', intent["text"]))
    else:
        if intent["options"]:
            st.session_state.history.append(
                ('Бот', "Мне не совсем ясно, уточните, пожалуйста:")
            )
            for opt in intent["options"]:
                st.session_state.history.append(('Вариант', opt))
        else:
            st.session_state.history.append(
                ('Бот', "Извините, я не понял запрос.")
            )

    st.session_state.msg_input = ''

# --- Старт приложения ---
init_db()
st.set_page_config(page_title="Чат-бот поддержки", layout="centered")

# --- Инициализация session_state ---
if 'started'         not in st.session_state: st.session_state.started = False
if 'history'         not in st.session_state: st.session_state.history = []
if 'msg_input'       not in st.session_state: st.session_state.msg_input = ''
if 'operator_online' not in st.session_state: st.session_state.operator_online = False

# --- Стартовый экран ---
if not st.session_state.started:
    st.title("Добро пожаловать в чат-поддержку!")
    st.write("Выберите тему или введите свой вопрос:")

    cats = [
      "Оплата", "Регистрация", "Техподдержка",
      "Сбои в работе", "Восстановление пароля", "Общие вопросы"
    ]
    cols = st.columns(3)
    for i, cat in enumerate(cats):
        if cols[i % 3].button(cat):
            st.session_state.started = True
            send_message(f"[Категория: {cat}]")

    inp = st.text_input("Или введите вопрос:", value=st.session_state.msg_input, key="msg_input")
    if st.button("Начать чат") and inp.strip():
        st.session_state.started = True
        send_message(inp)

    st.stop()

# --- Основной интерфейс чата ---
st.title("Чат-бот поддержки")

# **Кнопка возврата к категориям**
if st.button("🔙 Вернуться к категориям"):
    # Сброс состояния
    st.session_state.started = False
    st.session_state.history = []
    st.session_state.operator_online = False
    st.session_state.msg_input = ''
    # при нажатии на кнопку Streamlit автоматически перерисует экран
# Возможность показать индикатор оператора
if st.session_state.operator_online:
    st.info("🟢 Оператор онлайн")

# Вывод истории
for idx, (sender, msg) in enumerate(st.session_state.history):
    if sender == 'Вы':
        st.markdown(f"**Вы:** {msg}")
    elif sender == 'Бот':
        st.markdown(f"**Бот:** {msg}")
    else:  # Варианты уточнения
        if st.button(msg, key=f"opt_{idx}"):
            send_message(msg)

# Отправка по Enter
st.text_input(
    "Введите сообщение и нажмите Enter:",
    key="msg_input",
    value=st.session_state.msg_input,
    on_change=lambda: send_message(st.session_state.msg_input),
)

# Кнопка эскалации
if st.button("Связаться с оператором"):
    last = next((m for who,m in reversed(st.session_state.history) if who=='Вы'), '')
    _log_escalation(last)
    st.warning("Ваш запрос передан оператору.")
