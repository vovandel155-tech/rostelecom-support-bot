
import os
import pandas as pd
import streamlit as st
from datetime import datetime

# Paths to logs
BASE_DIR = os.path.dirname(__file__)
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
REQ_PATH = os.path.join(LOGS_DIR, 'requests.log')
MISSED_PATH = os.path.join(LOGS_DIR, 'missed.log')
ESC_PATH = os.path.join(LOGS_DIR, 'escalations.log')

st.set_page_config(page_title="Аналитика чат-бота", layout="wide")
st.title("📊 Дашборд аналитики чат-бота")

def load_log(path):
    """Read log file line by line, return DataFrame(text, timestamp)."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=['text','timestamp'])
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    df = pd.DataFrame({'text': lines})
    df['timestamp'] = pd.to_datetime(datetime.now().date())
    return df

# Load logs
df_req    = load_log(REQ_PATH)
df_missed = load_log(MISSED_PATH)
df_esc    = load_log(ESC_PATH)

# Metrics calculation with clamp
total_requests = len(df_req)
missed         = len(df_missed)
escalations    = len(df_esc)
successful     = total_requests - missed
# Prevent negative successful count
if successful < 0:
    successful = 0
hit_rate       = (successful / total_requests * 100) if total_requests else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Всего запросов",   total_requests)
col2.metric("Успешных ответов", f"{successful} ({hit_rate:.1f}%)")
col3.metric("Не понятых",        missed)
col4.metric("Эскалаций",         escalations)

st.markdown("---")

# Top 10 most frequent missed queries
if not df_missed.empty:
    st.subheader("🔍 Топ 10 непонятых запросов")
    top_missed = df_missed['text'].value_counts().head(10).reset_index()
    top_missed.columns = ['Запрос', 'Количество']
    st.table(top_missed)
else:
    st.info("Нет данных о непонятых запросах.")

# Plot requests over time (today only)
if not df_req.empty:
    st.subheader("📈 Количество запросов сегодня")
    daily = df_req.groupby('timestamp').size().reset_index(name='count')
    st.line_chart(daily.set_index('timestamp')['count'])
else:
    st.info("Нет данных о запросах.")

st.markdown(
    """
    **Инструкции:**  
    1. Сохраните этот файл как `analytics.py` рядом с `chat.py`.  
    2. Убедитесь, что в папке `logs/` есть файлы: `requests.log`,  
       `missed.log` и `escalations.log`.  
    3. Установите pandas, если ещё не:
       ```
       pip install pandas
       ```  
    4. Запустите:
       ```
       streamlit run analytics.py
       ```  
    5. Откройте в браузере http://localhost:8501.
    """
)
