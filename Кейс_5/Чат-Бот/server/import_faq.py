import os
import sqlite3
import csv

# определяем корень проекта
BASE_DIR = os.path.dirname(os.path.dirname(__file__))   # одна папка вверх от server/
DB_PATH  = os.path.join(BASE_DIR, 'data', 'db.sqlite')

conn = sqlite3.connect(DB_PATH)
c    = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS faq (
      id INTEGER PRIMARY KEY,
      category TEXT,
      question TEXT,
      answer TEXT
    );
''')

with open(os.path.join(BASE_DIR, 'faq.csv'), encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    for id,cat,q,a in reader:
        c.execute('INSERT OR REPLACE INTO faq VALUES (?,?,?,?)', (id,cat,q,a))

conn.commit()
conn.close()
print('FAQ imported into', DB_PATH)
