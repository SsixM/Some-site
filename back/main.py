from flask import Flask, jsonify

import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('menu.db')
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            image TEXT NOT NULL
        )
    ''')
    conn.commit()

    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM items')
    if cursor.fetchone()[0] == 0:
        items = [
            ('pizza', 'Маргарита', 'Томатный соус, моцарелла, свежий базилик, оливковое масло.', 550, 'src/images/photo_2025-10-18_23-47-09.jpg'),
            ('pizza', 'Пепперони', 'Томатный соус, моцарелла, острая колбаска пепперони.', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
            ('pizza', 'Четыре Сыра', 'Сливочный соус, моцарелла, дорблю, пармезан, чеддер.', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
            ('pasta', 'Карбонара', 'Спагетти, гуанчале, яичный желток, сыр пекорино романо, черный перец.', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
            ('pasta', 'Болоньезе', 'Тальятелле, мясной соус болоньезе (говядина, свинина, овощи), пармезан.', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
            ('drinks', 'Лимонад', 'Домашний, 0.5л', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
            ('drinks', 'Морс', 'Клюквенный, 0.5л', 550, 'src/images/photo_2025-10-18_23-47-091.jpg')
        ]
        conn.executemany('INSERT INTO items (category, name, description, price, image) VALUES (?, ?, ?, ?, ?)', items)
        conn.commit()

@app.route('/api/menu', methods=['GET'])
def get_menu():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()
    categories = {}
    for item in items:
        cat = item['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'id': item['id'],
            'name': item['name'],
            'description': item['description'],
            'price': item['price'],
            'image': item['image']
        })
    return jsonify({'categories': categories})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    app.run(debug=True, port=3000)