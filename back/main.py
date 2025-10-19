from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
import bcrypt
import sqlite3
import logging

app = Flask(__name__, static_folder='static')
CORS(app, supports_credentials=True)
SECRET_KEY = 'your-secret-key'

logging.basicConfig(level=logging.DEBUG)

# Фиксированный хэш для пароля '1'
# Сгенерирован с помощью: bcrypt.hashpw('1'.encode('utf-8'), bcrypt.gensalt())
users = [
    {
        'username': '1',
        'password': bcrypt.hashpw('1'.encode('utf-8'), bcrypt.gensalt())
    }
]

def get_db_connection():
    conn = sqlite3.connect('menu.db')
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

@app.route('/')
def home():
    return send_from_directory('static', 'login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    app.logger.debug(f'Login attempt: username={username}, password={password}')
    
    if not username or not password:
        app.logger.debug('Missing username or password')
        return jsonify({'error': 'Заполните все поля'}), 400

    user = next((u for u in users if u['username'] == username), None)
    if not user:
        app.logger.debug('User not found')
        return jsonify({'error': 'Пользователь не найден'}), 401
    
    if not bcrypt.checkpw(password.encode('utf-8'), user['password']):
        app.logger.debug('Password incorrect')
        return jsonify({'error': 'Неверный пароль'}), 401

    token = jwt.encode({'username': username}, SECRET_KEY, algorithm='HS256')
    app.logger.debug('Login successful, token generated')
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
        app.logger.debug('Missing required fields')
        return jsonify({'error': 'Заполните все обязательные поля'}), 400

    try:
        price = int(price)
        if price < 0:
            raise ValueError
    except ValueError:
        app.logger.debug('Invalid price format')
        return jsonify({'error': 'Цена должна быть положительным числом'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO items (category, name, description, price, image) VALUES (?, ?, ?, ?, ?)',
                   (category, name, description, price, image))
    conn.commit()
    conn.close()
    app.logger.debug(f'Dish added: {name} by {username}')
    return jsonify({'message': 'Блюдо успешно добавлено'})

@app.route('/api/remove-dish', methods=['POST'])
def remove_dish():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    dish_id = request.form.get('dish-id')
    if not dish_id:
        app.logger.debug('Missing dish-id')
        return jsonify({'error': 'Выберите блюдо для удаления'}), 400

    try:
        dish_id = int(dish_id)
    except ValueError:
        app.logger.debug('Invalid dish-id format')
        return jsonify({'error': 'Неверный ID блюда'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM items WHERE id = ?', (dish_id,))
    if not cursor.fetchone():
        conn.close()
        app.logger.debug(f'Dish not found: id={dish_id}')
        return jsonify({'error': 'Блюдо не найдено'}), 404

    cursor.execute('DELETE FROM items WHERE id = ?', (dish_id,))
    conn.commit()
    conn.close()
    app.logger.debug(f'Dish removed: id={dish_id} by {username}')
    return jsonify({'message': 'Блюдо успешно удалено'})

@app.route('/api/generate-table-link', methods=['POST'])
def generate_table_link():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    username, error, status = verify_token(token)
    if error:
        return jsonify(error), status

    table_number = request.form.get('table_number')
    if not table_number:
        app.logger.debug('Missing table_number')
        return jsonify({'error': 'Укажите номер столика'}), 400

    try:
        table_number = int(table_number)
        if table_number <= 0:
            raise ValueError
    except ValueError:
        app.logger.debug('Invalid table_number format')
        return jsonify({'error': 'Номер столика должен быть положительным числом'}), 400

    table_token = jwt.encode({'table_number': table_number}, SECRET_KEY, algorithm='HS256')
    link = f'file:///C:/Users/slava/Desktop/Defency/Some-site/redirect.html?lots={table_token}'
    app.logger.debug(f'Table link generated: {link} by {username}')
    return jsonify({'link': link})

@app.route('/api/verify-table', methods=['POST'])
def verify_table():
    table_token = request.json.get('lots')
    if not table_token:
        app.logger.debug('No table token provided')
        return jsonify({'error': 'Номер столика отсутствует'}), 400

    try:
        jwt.decode(table_token, SECRET_KEY, algorithms=['HS256'])
        app.logger.debug('Table token verified')
        return jsonify({'message': 'Токен валиден'})
    except jwt.InvalidTokenError:
        app.logger.debug('Invalid table token')
        return jsonify({'error': 'Неверный номер столика'}), 400

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
    app.run(port=3000, debug=True)