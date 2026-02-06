from flask import Flask, render_template, request, jsonify
from flask_admin import Admin
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib import sqla
from datetime import datetime
import json
import os
import time

# ===== PATH =====
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ===== APP =====
app = Flask(__name__, template_folder='templates', static_folder='static')
from flask import send_from_directory

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)
app.config['SECRET_KEY'] = 'your-secret-key-change-it'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'tag.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ===== MODELS =====
class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    city_id = db.Column(db.Integer, db.ForeignKey('city.id'))
    city = db.relationship('City', backref='locations')
    theme = db.Column(db.String(50))
    photos = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)

class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20))
    city = db.Column(db.String(100))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    user_id = db.Column(db.String(50))
    nickname = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SuggestionPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_title = db.Column(db.String(200))
    city = db.Column(db.String(100))
    filename = db.Column(db.String(200))
    user_id = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')

# ===== ADMIN =====
admin = Admin(app, name='THEARCGO Admin')
admin.add_view(sqla.ModelView(City, db.session))
admin.add_view(sqla.ModelView(Location, db.session))
admin.add_view(sqla.ModelView(Suggestion, db.session))
admin.add_view(sqla.ModelView(SuggestionPhoto, db.session))

# ===== API =====

# 🔹 ДОБАВЛЕНИЕ ГОРОДА ИЗ ВЕБА
@app.route('/api/add-city', methods=['POST'])
def add_city():
    if not request.is_json:
        return jsonify({'error': 'Expected JSON'}), 400

    data = request.get_json(silent=True)
    name = data.get('name')
    slug = data.get('slug')

    if not name or not slug:
        return jsonify({'error': 'name and slug required'}), 400

    if City.query.filter_by(slug=slug).first():
        return jsonify({'error': 'city already exists'}), 400

    city = City(name=name, slug=slug)
    db.session.add(city)
    db.session.commit()

    return jsonify({'status': 'ok'})

# 🔹 ПРЕДЛОЖЕНИЯ
@app.route('/api/suggest', methods=['POST'])
def suggest():
    if not request.is_json:
        return jsonify({'error': 'Expected JSON'}), 400

    data = request.get_json(silent=True)

    suggestion = Suggestion(
        type=data.get('type'),
        city=data.get('city'),
        title=data.get('title'),
        description=data.get('description'),
        user_id=data.get('user_id'),
        nickname=data.get('nickname')
    )

    db.session.add(suggestion)
    db.session.commit()

    return jsonify({'status': 'ok'})

# 🔹 ГОРОДА
@app.route('/api/cities')
def get_cities():
    cities = City.query.all()
    return jsonify([{'name': c.name, 'slug': c.slug} for c in cities])

# 🔹 ЛОКАЦИИ
@app.route('/api/locations/<city_slug>')
def get_locations(city_slug):
    city = City.query.filter_by(slug=city_slug).first()
    if not city:
        return jsonify([])

    locations = Location.query.filter_by(city_id=city.id, approved=True).all()

    def _parse_themes(val):
        if not val:
            return ['popular']
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, str):
                return [parsed]
        except Exception:
            return [val]

    return jsonify([
        {
            'title': l.title,
            'desc': l.description or '',
            'themes': _parse_themes(l.theme),
            'photos': json.loads(l.photos or '[]')
        } for l in locations
    ])

# 🔹 ФОТО
@app.route('/api/photo-suggest', methods=['POST'])
def photo_suggest():
    files = request.files.getlist('photos')
    location = request.form.get('location')
    city = request.form.get('city')
    user_id = request.form.get('user_id')

    os.makedirs('uploads/photos_pending', exist_ok=True)

    for file in files:
        if file and file.filename:
            filename = f"{user_id}_{int(time.time())}_{file.filename}"
            file.save(f"uploads/photos_pending/{filename}")

            photo = SuggestionPhoto(
                location_title=location,
                city=city,
                filename=filename,
                user_id=user_id,
                status='pending'
            )
            db.session.add(photo)

    db.session.commit()
    return jsonify({'success': True})

# ===== SITE =====
@app.route("/")
def index():
    return render_template("index.html")

# ===== RUN =====
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("✅ БД готова")
        print("Cities:", City.query.count())

    print("🚀 http://localhost:8000/")
    print("👑 http://localhost:8000/admin/")

    app.run(host="0.0.0.0", port=8000, debug=True)

