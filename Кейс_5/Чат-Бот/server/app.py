from flask import (
    Flask, render_template_string, redirect, url_for,
    request, send_file, make_response
)
import os
import sqlite3
import csv
import io
import json

app = Flask(__name__)

# Путь к файлам
BASE_DIR    = os.path.dirname(__file__)          # server/
LOGS_DIR    = os.path.join(BASE_DIR, '..', 'logs')
DATA_DIR    = os.path.join(BASE_DIR, '..', 'data')
DB_PATH     = os.path.join(DATA_DIR, 'db.sqlite')
ESC_PATH    = os.path.join(LOGS_DIR, 'escalations.log')
MISSED_PATH = os.path.join(LOGS_DIR, 'missed.log')
REQ_PATH    = os.path.join(LOGS_DIR, 'requests.log')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- ПЕРЕНАПРАВЛЕНИЕ НА OPERATOR ПО УМОЛЧАНИЮ ---
@app.route('/')
def home():
    return redirect(url_for('operator_panel'))

# --- ПАНЕЛЬ ОПЕРАТОРА ---
@app.route('/operator')
def operator_panel():
    # Читаем эскалированные запросы
    if os.path.exists(ESC_PATH):
        with open(ESC_PATH, encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
    else:
        lines = []
    template = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Панель оператора</title></head>
    <body>
      <h1>Эскалированные запросы</h1>
      {% if lines %}
        <ol>{% for q in lines %}<li>{{ q }}</li>{% endfor %}</ol>
      {% else %}
        <p>Нет новых эскалированных запросов.</p>
      {% endif %}
      <p><a href="{{ url_for('analytics_panel') }}">→ Аналитика</a> |
         <a href="{{ url_for('admin_panel') }}">→ Администрирование</a></p>
    </body>
    </html>
    """
    return render_template_string(template, lines=lines)

# --- ПАНЕЛЬ АНАЛИТИКИ ---
@app.route('/analytics')
def analytics_panel():
    def count_lines(path):
        if not os.path.exists(path): return 0
        with open(path, encoding='utf-8') as f:
            return sum(1 for _ in f)
    total  = count_lines(REQ_PATH)
    missed = count_lines(MISSED_PATH)
    escal  = count_lines(ESC_PATH)
    success = total - missed
    hit_rate = (success/total*100) if total>0 else 0
    template = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Аналитика бота</title></head>
    <body>
      <h1>Аналитика чат-бота</h1>
      <ul>
        <li>Всего запросов: {{ total }}</li>
        <li>Успешных ответов: {{ success }} ({{ hit_rate|round(1) }}%)</li>
        <li>Не понятых: {{ missed }}</li>
        <li>Эскалаций к оператору: {{ escal }}</li>
      </ul>
      <p><a href="{{ url_for('operator_panel') }}">← Оператор</a> |
         <a href="{{ url_for('admin_panel') }}">→ Администрирование</a></p>
    </body>
    </html>
    """
    return render_template_string(template,
                                  total=total, success=success,
                                  hit_rate=hit_rate, missed=missed, escal=escal)

# --- АДМИН-ПАНЕЛЬ (CRUD + импорт/экспорт) ---

# Форма списка Q&A
@app.route('/admin')
def admin_panel():
    conn = get_db()
    rows = conn.execute("SELECT id,category,question,answer FROM faq").fetchall()
    conn.close()
    template = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Администрирование Q&A</title></head>
    <body>
      <h1>Управление базой знаний</h1>
      <p>
        <a href="{{ url_for('admin_add') }}">Добавить запись</a> |
        <a href="{{ url_for('admin_export', fmt='csv') }}">Export CSV</a> |
        <a href="{{ url_for('admin_export', fmt='json') }}">Export JSON</a> |
        <a href="{{ url_for('admin_import') }}">Import CSV/JSON</a> |
        <a href="{{ url_for('operator_panel') }}">← Оператор</a>
      </p>
      <table border="1" cellpadding="4" cellspacing="0">
        <tr><th>ID</th><th>Категория</th><th>Вопрос</th><th>Ответ</th><th>Действия</th></tr>
        {% for r in rows %}
        <tr>
          <td>{{ r.id }}</td>
          <td>{{ r.category }}</td>
          <td>{{ r.question }}</td>
          <td>{{ r.answer }}</td>
          <td>
            <a href="{{ url_for('admin_edit', id=r.id) }}">Edit</a> |
            <a href="{{ url_for('admin_delete', id=r.id) }}" 
               onclick="return confirm('Удалить запись {{ r.id }}?');">Delete</a>
          </td>
        </tr>
        {% endfor %}
      </table>
    </body>
    </html>
    """
    return render_template_string(template, rows=rows)

# Добавление новой записи
@app.route('/admin/add', methods=['GET','POST'])
def admin_add():
    if request.method=='POST':
        cat = request.form['category']
        q   = request.form['question']
        a   = request.form['answer']
        conn = get_db()
        conn.execute("INSERT INTO faq(category,question,answer) VALUES(?,?,?)",
                     (cat,q,a))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_panel'))
    # GET
    form = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Добавить запись</title></head>
    <body>
      <h1>Добавить запись</h1>
      <form method="post">
        Категория:<br><input name="category"><br>
        Вопрос:<br><textarea name="question" rows="2" cols="50"></textarea><br>
        Ответ:<br><textarea name="answer" rows="3" cols="50"></textarea><br>
        <button type="submit">Сохранить</button>
      </form>
      <p><a href="{{ url_for('admin_panel') }}">← Назад</a></p>
    </body>
    </html>
    """
    return render_template_string(form)

# Редактирование записи
@app.route('/admin/edit/<int:id>', methods=['GET','POST'])
def admin_edit(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM faq WHERE id=?", (id,)).fetchone()
    if request.method=='POST':
        conn.execute("UPDATE faq SET category=?,question=?,answer=? WHERE id=?",
                     (request.form['category'],
                      request.form['question'],
                      request.form['answer'], id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_panel'))
    # GET
    form = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Редактировать запись</title></head>
    <body>
      <h1>Редактировать запись {{ row.id }}</h1>
      <form method="post">
        Категория:<br><input name="category" value="{{ row.category }}"><br>
        Вопрос:<br><textarea name="question" rows="2" cols="50">{{ row.question }}</textarea><br>
        Ответ:<br><textarea name="answer" rows="3" cols="50">{{ row.answer }}</textarea><br>
        <button type="submit">Сохранить</button>
      </form>
      <p><a href="{{ url_for('admin_panel') }}">← Назад</a></p>
    </body>
    </html>
    """
    conn.close()
    return render_template_string(form, row=row)

# Удаление записи
@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    conn = get_db()
    conn.execute("DELETE FROM faq WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

# Экспорт CSV/JSON
@app.route('/admin/export/<fmt>')
def admin_export(fmt):
    conn = get_db()
    rows = conn.execute("SELECT id,category,question,answer FROM faq").fetchall()
    conn.close()
    if fmt=='json':
        data = [dict(r) for r in rows]
        return Response(json.dumps(data, ensure_ascii=False, indent=2),
                        mimetype='application/json',
                        headers={"Content-Disposition":"attachment;filename=faq.json"})
    # default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(('id','category','question','answer'))
    for r in rows:
        writer.writerow((r['id'], r['category'], r['question'], r['answer']))
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=faq.csv"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp

# Импорт CSV или JSON
@app.route('/admin/import', methods=['GET','POST'])
def admin_import():
    if request.method=='POST':
        f = request.files['file']
        if not f:
            return "Файл не загружен", 400
        data = f.read()
        conn = get_db()
        c = conn.cursor()
        # простейшая очистка старой таблицы
        c.execute("DELETE FROM faq")
        conn.commit()
        # определяем расширение
        name = f.filename.lower()
        if name.endswith('.json'):
            items = json.loads(data.decode('utf-8'))
            for item in items:
                c.execute("INSERT INTO faq VALUES (?,?,?,?)",
                          (item['id'], item['category'], item['question'], item['answer']))
        else:  # csv
            text = data.decode('utf-8-sig').splitlines()
            reader = csv.reader(text)
            next(reader)
            for id,cat,q,a in reader:
                c.execute("INSERT INTO faq VALUES (?,?,?,?)",
                          (id,cat,q,a))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_panel'))
    # GET: форма загрузки
    form = """
    <!doctype html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Import Q&A</title></head>
    <body>
      <h1>Импортировать базу</h1>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".csv,.json"><br><br>
        <button type="submit">Загрузить</button>
      </form>
      <p><a href="{{ url_for('admin_panel') }}">← Назад</a></p>
    </body>
    </html>
    """
    return render_template_string(form)

if __name__ == '__main__':
    app.run(debug=True)
