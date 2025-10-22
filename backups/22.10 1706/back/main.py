from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
import bcrypt
import sqlite3
import logging
import json
import os

app = Flask(__name__, static_folder='static')
CORS(app, supports_credentials=True)
SECRET_KEY = 'your-secret-key'

logging.basicConfig(level=logging.DEBUG)

# Фиксированный пользователь
users = [
    {
        'username': '1',
        'password': bcrypt.hashpw('1'.encode('utf-8'), bcrypt.gensalt())
    }
]

DB_NAME = 'menu.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def verify_token(token):
    if not token:
        app.logger.debug('No token provided')
        return None, {'error': 'Токен отсутствует'}, 401
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        username = data['username']
        user = next((u for u in users if u['username'] == username), None)
        if not user:
            app.logger.debug('User from token not found')
            return None, {'error': 'Пользователь не найден'}, 401
        app.logger.debug('Token valid')
        return username, None, None
    except jwt.ExpiredSignatureError:
        app.logger.debug('Token expired')
        return None, {'error': 'Сессия истекла'}, 401
    except jwt.InvalidTokenError:
        app.logger.debug('Invalid token')
        return None, {'error': 'Неверный токен'}, 401

def init_db():
    with get_db_connection() as conn:
        # Таблица блюд
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

        # Таблица заказов
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                items TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

        # Заполнение меню, если пусто
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM items')
        if cursor.fetchone()[0] == 0:
            items = [

                ('pizza', 'Маргарита', 'Томатный соус, моцарелла, свежий базилик, оливковое масло.', 550, 'https://mixthatdrink.com/wp-content/uploads/2023/03/classic-margarita-cocktail-540x720.jpg'),
                ('pizza', 'Пепперони', 'Томатный соус, моцарелла, острая колбаска пепперони.', 550, 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTfdW8M3-Gps9QKZssNfNSiyn-ppKZmotyzug&s'),
                ('pizza', 'Четыре Сыра', 'Сливочный соус, моцарелла, дорблю, пармезан, чеддер.', 550, 'https://cafebrynza.ru/goods/789.jpg'),
                ('pasta', 'Карбонара', 'Спагетти, гуанчале, яичный желток, сыр пекорино романо, черный перец.', 550, 'https://i0.wp.com/kjsfoodjournal.com/wp-content/uploads/2020/09/carbonara.png'),
                ('pasta', 'Болоньезе', 'Тальятелле, мясной соус болоньезе (говядина, свинина, овощи), пармезан.', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
                ('drinks', 'Лимонад', 'Домашний, 0.5л', 550, 'src/images/photo_2025-10-18_23-47-091.jpg'),
                ('drinks', 'Морс', 'Клюквенный, 0.5л', 550, 'src/images/photo_2025-10-18_23-47-091.jpg')
            ]
            conn.executemany('INSERT INTO items (category, name, description, price, image) VALUES (?, ?, ?, ?, ?)', items)
            conn.commit()

def migrate_db():
    if not os.path.exists(DB_NAME):
        init_db()
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'user_name' not in columns:
            app.logger.info("Migrating orders table...")
            conn.execute('ALTER TABLE orders RENAME TO orders_old')
            conn.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    items TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                conn.execute('''
                    INSERT INTO orders (id, user_name, phone, items, total, status)
                    SELECT id, name, phone, items, total, status FROM orders_old
                ''')
            except sqlite3.OperationalError as e:
                app.logger.warning(f"Migration failed (old data incompatible): {e}")
            finally:
                conn.execute('DROP TABLE IF EXISTS orders_old')
            conn.commit()

@app.route('/')
def home():
    return send_from_directory('static', 'login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Заполните все поля'}), 400

    user = next((u for u in users if u['username'] == username), None)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 401
    
    if not bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'error': 'Неверный пароль'}), 401

    token = jwt.encode({'username': username}, SECRET_KEY, algorithm='HS256')
    return jsonify({'token': token})

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

@app.route('/api/add-dish', methods=['POST'])
def add_dish():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    data = request.form
    name = data.get('name')
    category = data.get('category')
    description = data.get('description')
    price = data.get('price')
    image = data.get('image') or 'src/images/default.jpg'

    if not all([name, category, description, price]):
        return jsonify({'error': 'Заполните все обязательные поля'}), 400

    try:
        price = int(price)
        if price < 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': 'Цена должна быть положительным числом'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO items (category, name, description, price, image) VALUES (?, ?, ?, ?, ?)',
                   (category, name, description, price, image))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Блюдо успешно добавлено'})

@app.route('/api/remove-dish', methods=['POST'])
def remove_dish():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    dish_id = request.form.get('dish-id')
    if not dish_id:
        return jsonify({'error': 'Выберите блюдо для удаления'}), 400

    try:
        dish_id = int(dish_id)
    except ValueError:
        return jsonify({'error': 'Неверный ID блюда'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM items WHERE id = ?', (dish_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Блюдо не найдено'}), 404

    cursor.execute('DELETE FROM items WHERE id = ?', (dish_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Блюдо успешно удалено'})

@app.route('/api/generate-table-link', methods=['POST'])
def generate_table_link():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    table_number = request.form.get('table_number')
    if not table_number:
        return jsonify({'error': 'Укажите номер столика'}), 400

    try:
        table_number = int(table_number)
        if table_number <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': 'Номер столика должен быть положительным числом'}), 400

    table_token = jwt.encode({'table_number': table_number}, SECRET_KEY, algorithm='HS256')
    link = f'file:///C:/Users/slava/Desktop/Defency/Some-site/redirect.html?lots={table_token}'
    return jsonify({'link': link})

@app.route('/api/verify-table', methods=['POST'])
def verify_table():
    table_token = request.json.get('lots')
    if not table_token:
        return jsonify({'error': 'Номер столика отсутствует'}), 400

    try:
        jwt.decode(table_token, SECRET_KEY, algorithms=['HS256'])
        return jsonify({'message': 'Токен валиден'})
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Неверный номер столика'}), 400

@app.route('/api/create-order', methods=['POST'])
def create_order():
    data = request.json
    user_name = data.get('user_name')
    phone = data.get('phone')
    cart = data.get('cart')

    if not all([user_name, phone, cart]):
        return jsonify({'error': 'Заполните все поля'}), 400

    try:
        total = sum(item['price'] * item['quantity'] for item in cart)
    except Exception as e:
        app.logger.error(f"Invalid cart format: {e}")
        return jsonify({'error': 'Неверный формат корзины'}), 400

    items_json = json.dumps(cart)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_name, phone, items, total, status)
        VALUES (?, ?, ?, ?, 'new')
    ''', (user_name, phone, items_json, total))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()

    return jsonify({'message': 'Заказ успешно создан', 'order_id': order_id})

@app.route('/api/orders', methods=['GET'])
def get_orders():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()

    orders_list = []
    for order in orders:
        orders_list.append({
            'id': order['id'],
            'user_name': order['user_name'],
            'phone': order['phone'],
            'items': json.loads(order['items']),
            'total': order['total'],
            'status': order['status'],
            'timestamp': order['created_at']
        })

    return jsonify({'orders': orders_list})

@app.route('/api/take-order/<int:order_id>', methods=['POST'])
def take_order(order_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM orders WHERE id = ?', (order_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Заказ не найден'}), 404

    if result['status'] != 'new':
        conn.close()
        return jsonify({'error': 'Заказ уже взят или закрыт'}), 400

    cursor.execute('UPDATE orders SET status = "in_progress" WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Заказ взят в работу'})

@app.route('/api/close-order/<int:order_id>', methods=['POST'])
def close_order(order_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM orders WHERE id = ?', (order_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Заказ не найден'}), 404

    if result['status'] == 'closed':
        conn.close()
        return jsonify({'error': 'Заказ уже закрыт'}), 400

    cursor.execute('UPDATE orders SET status = "closed" WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Заказ закрыт'})

@app.route('/logout')
def logout():
    return jsonify({'message': 'Logged out'})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

if __name__ == '__main__':
    migrate_db()
    app.run(port=3000, debug=True)