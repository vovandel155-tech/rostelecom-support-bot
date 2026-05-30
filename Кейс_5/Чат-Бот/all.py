import streamlit as st
import os
import sqlite3
import csv
import re
from datetime import datetime
# Админ-пароль для входа (для учебного проекта хранится прямо в коде)
ADMIN_PW = "1234"

# Флаг того, что админ уже залогинен
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# Загружаем пароль администратора из секретов
ADMIN_PW = st.secrets["admin"]["password"]

# Инициализируем флаг авторизации
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# ──────────────────────────────────────────────────────────────────────────────
# Пути и константы
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
DB_PATH      = os.path.join(BASE_DIR, 'data', 'db.sqlite')
CSV_PATH     = os.path.join(BASE_DIR, 'faq.csv')
LOGS_DIR     = os.path.join(BASE_DIR, 'logs')
REQ_PATH     = os.path.join(LOGS_DIR, 'requests.log')
MISSED_PATH  = os.path.join(LOGS_DIR, 'missed.log')
ESC_PATH     = os.path.join(LOGS_DIR, 'escalations.log')
FEEDBACK_PATH= os.path.join(LOGS_DIR, 'feedback.log')
SUGGEST_PATH = os.path.join(LOGS_DIR, 'suggestions.log')

CLARIFY_THRESHOLD = 1
MAX_OPTIONS       = 3

# ──────────────────────────────────────────────────────────────────────────────
# Утилиты работы с логами
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_logs():
    os.makedirs(LOGS_DIR, exist_ok=True)

def log_request(text):
    _ensure_logs()
    with open(REQ_PATH,'a',encoding='utf-8') as f:
        f.write(f"{datetime.now().isoformat()}|{text}\n")

def log_missed(text):
    _ensure_logs()
    with open(MISSED_PATH,'a',encoding='utf-8') as f:
        f.write(f"{datetime.now().isoformat()}|{text}\n")

def log_escalation(text):
    _ensure_logs()
    with open(ESC_PATH,'a',encoding='utf-8') as f:
        f.write(f"{datetime.now().isoformat()}|{text}\n")
    st.session_state.operator_online = True

def log_feedback(q, a, rating):
    _ensure_logs()
    with open(FEEDBACK_PATH,'a',encoding='utf-8') as f:
        f.write(f"{datetime.now().isoformat()}|{rating}|Q:{q}|A:{a}\n")

def log_suggestion(q, suggestion):
    _ensure_logs()
    with open(SUGGEST_PATH,'a',encoding='utf-8') as f:
        f.write(f"{datetime.now().isoformat()}|Q:{q}|Suggestion:{suggestion}\n")

# ──────────────────────────────────────────────────────────────────────────────
# NLP и инициализация базы
# ──────────────────────────────────────────────────────────────────────────────
def extract_keywords(text):
    return re.findall(r'\b[А-Яа-яA-Za-z0-9Ёё]+\b', text.lower())

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS faq (
                    id INTEGER PRIMARY KEY,
                    category TEXT,
                    question TEXT,
                    answer TEXT
                 );""")
    conn.commit()
    c.execute("SELECT COUNT(*) FROM faq")
    if c.fetchone()[0] == 0:
        with open(CSV_PATH, encoding='utf-8-sig') as f:
            reader = csv.reader(f); next(reader)
            for id,cat,q,a in reader:
                c.execute("INSERT OR REPLACE INTO faq VALUES (?,?,?,?)",
                          (id,cat,q,a))
        conn.commit()
    conn.close()

def find_intent(text):
    kws = extract_keywords(text)
    if not kws:
        return {"type":"clarify","options":[], "text":None}
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT question,answer FROM faq")
    rows = c.fetchall(); conn.close()
    scored = [(sum(kw in q.lower() for kw in kws), q, a) for q,a in rows]
    scored = [s for s in scored if s[0]>0]
    if not scored:
        return {"type":"clarify","options":[], "text":None}
    scored.sort(key=lambda x:x[0], reverse=True)
    best_score,best_q,best_a = scored[0]
    if best_score < CLARIFY_THRESHOLD:
        opts = [q for _,q,_ in scored[:MAX_OPTIONS]]
        return {"type":"clarify","options":opts,"text":None}
    return {"type":"answer","options":[],"text":best_a}

# ──────────────────────────────────────────────────────────────────────────────
# Старт приложения
# ──────────────────────────────────────────────────────────────────────────────
init_db()
st.set_page_config(page_title="Чат-бот & Обучение", layout="wide")

# ──────────────────────────────────────────────────────────────────────────────
# Состояние сессии
# ──────────────────────────────────────────────────────────────────────────────
if 'history'         not in st.session_state: st.session_state.history = []
if 'msg_input'       not in st.session_state: st.session_state.msg_input = ''
if 'started'         not in st.session_state: st.session_state.started = False
if 'operator_online' not in st.session_state: st.session_state.operator_online = False
if 'feedback_count'  not in st.session_state: st.session_state.feedback_count = 0
if 'last_q'          not in st.session_state: st.session_state.last_q = ''
if 'last_a'          not in st.session_state: st.session_state.last_a = ''

# ──────────────────────────────────────────────────────────────────────────────
# Меню: чёрт-бот и аналитика
# ──────────────────────────────────────────────────────────────────────────────
# Формируем список доступных страниц

page = st.sidebar.selectbox("Меню", ["Чат-бот", "Аналитика"])
# Если выбрали аналитику, но ещё не вошли — показываем форму логина

if page == "Аналитика" and not st.session_state.is_admin:
    st.title("🔐 Вход для администратора")
    pwd = st.text_input("Пароль администратора:", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PW:
            st.session_state.is_admin = True
            st.success("Вход выполнен! Теперь переходите в раздел «Аналитика».")
        else:
            st.error("Неверный пароль")
    # Прекращаем дальнейшую отрисовку до логина
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# 1) Чат-бот
# ──────────────────────────────────────────────────────────────────────────────
if page == "Чат-бот":
    st.title("💬 Чат-бот поддержки")

    if st.sidebar.button("🔙 Сбросить чат"):
        st.session_state.started = False
        st.session_state.history = []
        st.session_state.operator_online = False
        st.session_state.msg_input = ''
        st.session_state.feedback_count = 0

    # --- Стартовый экран ---
    if not st.session_state.started:
        st.write("Добро пожаловать! Выберите тему или задайте вопрос:")
        cats = ["Оплата","Регистрация","Техподдержка",
                "Сбои в работе","Восстановление пароля","Общие вопросы"]
        cols = st.columns(3)
        for i,cat in enumerate(cats):
            if cols[i%3].button(cat):
                st.session_state.started = True
                q = f"[Категория: {cat}]"
                log_request(q); st.session_state.history.append(("Вы",q))
                intent = find_intent(q)
                if intent["type"]=="answer":
                    st.session_state.history.append(("Бот", intent["text"]))
                else:
                    log_missed(q)
                    st.session_state.history.append(("Бот","Извините, не понял запрос."))
                    st.session_state.last_q, st.session_state.last_a = q, None
                    # prepare feedback
                st.experimental_rerun()
        inp = st.text_input("Или введите свой вопрос:", key="msg_input")
        if st.button("Начать чат") and inp.strip():
            st.session_state.started = True
            log_request(inp.strip())
            st.session_state.history.append(("Вы",inp.strip()))
            intent = find_intent(inp.strip())
            if intent["type"]=="answer":
                st.session_state.history.append(("Бот", intent["text"]))
                st.session_state.last_q, st.session_state.last_a = inp.strip(), intent["text"]
            else:
                log_missed(inp.strip())
                st.session_state.history.append(("Бот","Извините, не понял запрос."))
                st.session_state.last_q, st.session_state.last_a = inp.strip(), None
            st.experimental_rerun()
        st.write("Это страница чат-бота")
        st.stop()
    if page == "Чат-бот":
        # Кнопка «Вернуться к категориям»
        if st.sidebar.button("🔙 Вернуться к категориям"):
            # Сбрасываем выбор категории и историю
            st.session_state.started = False
            st.session_state.history = []
            st.session_state.msg_input = ''
            st.session_state.operator_online = False
            # После клика весь блок перерисуется, и вы снова попадёте на стартовый экран


    # --- Основной чат ---
    if st.session_state.operator_online:
        st.info("🟢 Оператор онлайн")
    for who,msg in st.session_state.history:
        if who=="Вы": st.markdown(f"**Вы:** {msg}")
        else:         st.markdown(f"**Бот:** {msg}")

    # --- Отправка по Enter ---
    def _send():
        txt = st.session_state.msg_input.strip()
        if not txt: return
        log_request(txt)
        st.session_state.history.append(("Вы",txt))
        intent = find_intent(txt)
        if intent["type"]=="answer":
            with st.spinner("Бот печатает…"):
                ans = intent["text"]
            st.session_state.history.append(("Бот",ans))
            st.session_state.last_q, st.session_state.last_a = txt, ans
        else:
            log_missed(txt)
            st.session_state.history.append(("Бот","Извините, не понял запрос."))
            st.session_state.last_q, st.session_state.last_a = txt, None
        st.session_state.msg_input = ''
    st.text_input("Введите сообщение и нажмите Enter:",
                  key="msg_input",
                  value=st.session_state.msg_input,
                  on_change=_send)

    # --- Кнопка эскалации ---
    if st.button("Связаться с оператором"):
        last = next((m for who,m in reversed(st.session_state.history) if who=="Вы"),"")
        log_escalation(last)
        st.warning("Запрос передан оператору.")

    # --- Модуль обучения: оценка и предложения ---
    # Сколько бот уже отвечал?
    bot_count = sum(1 for who,_ in st.session_state.history if who=="Бот")
    # Нужна ли оценка
    if bot_count > st.session_state.feedback_count:
        q = st.session_state.last_q
        a = st.session_state.last_a or ""
        st.write("---")
        st.write("Был ли ответ полезен?")
        c1, c2 = st.columns(2)
        if c1.button("👍 Полезно"):
            log_feedback(q, a, "yes")
            st.success("Спасибо за ваш отзыв!")
            st.session_state.feedback_count += 1
        if c2.button("👎 Не полезно"):
            log_feedback(q, a, "no")
            st.write("Пожалуйста, предложите, как бот мог ответить:")
            suggestion = st.text_area("", key="suggest")
            if st.button("Отправить предложение"):
                log_suggestion(q, suggestion)
                st.success("Спасибо, мы учтём ваше предложение!")
                st.session_state.feedback_count += 1

# ──────────────────────────────────────────────────────────────────────────────
# 2) Аналитика
# ──────────────────────────────────────────────────────────────────────────────
else:
    import pandas as pd

    if page == "Аналитика" and st.session_state.is_admin:
        if st.sidebar.button("🚪 Выйти"):
            st.session_state.is_admin = False
            st.success("Вы вышли из режима администратора.")
            st.stop()
    st.title("📊 Дашборд аналитики")

    def load_log(path):
        """
        Читает лог-файл построчно.
        Если строка содержит '|', берет всё после первого '|', иначе — всю строку.
        Возвращает DataFrame с колонками ['text','ts'].
        """
        import pandas as pd
        from datetime import datetime

        if not os.path.exists(path):
            return pd.DataFrame(columns=['text', 'ts'])
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                # если есть разделитель, убираем префикс с датой
                if '|' in s:
                    parts = s.split('|', 1)
                    text = parts[1]
                else:
                    text = s
                lines.append(text)
        # собираем DataFrame
        df = pd.DataFrame({'text': lines})
        # присваиваем всем записям сегодняшнюю дату (для простоты)
        df['ts'] = pd.to_datetime(datetime.now().date())
        return df


    df_req    = load_log(REQ_PATH)
    df_missed = load_log(MISSED_PATH)
    df_esc    = load_log(ESC_PATH)
    df_feed   = load_log(FEEDBACK_PATH)

    total   = len(df_req)
    missed  = len(df_missed)
    escal   = len(df_esc)
    suc     = max(0, total - missed)
    hit     = (suc/total*100) if total else 0
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Всего запросов",     total)
    c2.metric("Успешных ответов",   f"{suc} ({hit:.1f}%)")
    c3.metric("Не понятых",          missed)
    c4.metric("Эскалаций",           escal)

    st.markdown("---")
    if not df_missed.empty:
        st.subheader("🔍 Топ-10 непонятых")
        top=df_missed['text'].value_counts().head(10).reset_index()
        top.columns=['Запрос','Частота']
        st.table(top)
    if not df_feed.empty:
        st.subheader("👍 Отзывы пользователей")
        fb=df_feed['text'].value_counts().head(5).reset_index()
        fb.columns=['Вид','Частота']
        st.table(fb)

    st.markdown("---")
    if not df_req.empty:
        st.subheader("📈 Запросы сегодня")
        daily=df_req.groupby('ts').size().reset_index(name='count')
        st.line_chart(daily.set_index('ts')['count'])
