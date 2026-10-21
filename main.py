import sqlite3
import os
import math
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash
from config import DATABASE

import matplotlib

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

matplotlib.use('Agg')
app = Flask(__name__)
app.secret_key = "dev-secret-key"


class DB_Map():
    def __init__(self, database):
        self.database = database
        self.create_cities_table()

    def _get_conn(self):
        return sqlite3.connect(self.database)

    def create_cities_table(self):
        conn = self._get_conn()
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS cities (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                city TEXT UNIQUE NOT NULL,
                                lat REAL NOT NULL,
                                lng REAL NOT NULL
                            )''')
            conn.commit()

    def create_user_table(self):
        conn = self._get_conn()
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users_cities (
                                user_id INTEGER,
                                city_id INTEGER,
                                FOREIGN KEY(city_id) REFERENCES cities(id)
                            )''')
            conn.commit()

    def add_city(self, user_id, city_name, lat=None, lng=None):
        conn = self._get_conn()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, lat, lng FROM cities WHERE city=?",
                           (city_name,))
            city_data = cursor.fetchone()
            if city_data:
                city_id = city_data[0]
                cursor.execute('''INSERT OR IGNORE INTO
                               users_cities VALUES (?, ?)''',
                               (user_id, city_id))
                conn.commit()
                return 1
            else:
                if lat is None or lng is None:
                    return 0
                cursor.execute('''INSERT INTO cities
                               (city, lat, lng) VALUES (?, ?, ?)''',
                               (city_name, lat, lng))
                city_id = cursor.lastrowid
                cursor.execute('INSERT INTO users_cities VALUES (?, ?)',
                               (user_id, city_id))
                conn.commit()
                return 1

    def remove_city(self, user_id, city_name):
        conn = self._get_conn()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM cities WHERE city=?", (city_name,))
            row = cursor.fetchone()
            if not row:
                return False
            city_id = row[0]
            cursor.execute(
                "DELETE FROM users_cities WHERE user_id=? AND city_id=?",
                (user_id, city_id)
            )
            return True

    def select_cities(self, user_id):
        conn = self._get_conn()
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT cities.city
                            FROM users_cities
                            JOIN cities ON users_cities.city_id = cities.id
                            WHERE users_cities.user_id = ?''', (user_id,))
            cities = [row[0] for row in cursor.fetchall()]
            return cities

    def get_coordinates(self, city_name):
        conn = self._get_conn()
        with conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT lat, lng
                            FROM cities
                            WHERE city = ?''', (city_name,))
            coordinates = cursor.fetchone()
            return coordinates

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0  # радиус Земли в км
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        b2 = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2)
        a = b2 * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def draw_distance(self, city1, city2):
        coords1 = self.get_coordinates(city1)
        coords2 = self.get_coordinates(city2)
        if not coords1 or not coords2:
            return None
        lat1, lng1 = coords1
        lat2, lng2 = coords2
        distance = self.haversine(lat1, lng1, lat2, lng2)
        return distance

    def create_graph(self, path, cities):
        coords = []
        for city in cities:
            c = self.get_coordinates(city)
            if c:
                coords.append((c[1], c[0]))  # lon, lat

        if len(coords) < 2:
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_global()
            ax.coastlines()
            ax.add_feature(cfeature.LAND, facecolor='lightgreen',
                           edgecolor='black', alpha=0.7)
            ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.6)
            ax.add_feature(cfeature.BORDERS, linestyle=':', edgecolor='gray',
                           alpha=0.5)

            if coords:
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                colors = plt.cm.viridis(np.linspace(0, 1, len(coords)))
                ax.scatter(lons, lats, transform=ccrs.PlateCarree(),
                           color=colors, s=100, edgecolors='black',
                           linewidth=1.5, zorder=3)
                for i, city in enumerate(cities):
                    ax.text(lons[i], lats[i] + 0.5, city,
                            transform=ccrs.PlateCarree(), fontsize=11,
                            ha='center', va='bottom',
                            bbox=dict(boxstyle="round,pad=0.3",
                                      facecolor='white', alpha=0.8))

            plt.savefig(path, dpi=150, bbox_inches='tight')
            plt.close()
            return

        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_global()
        ax.coastlines()

        # Цветной фон карты
        ax.add_feature(cfeature.LAND, facecolor='lightgreen',
                       edgecolor='black', alpha=0.7)
        ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.6)
        ax.add_feature(cfeature.BORDERS, linestyle='-', edgecolor='gray')
        ax.add_feature(cfeature.LAKES, facecolor='skyblue', alpha=0.5)
        ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5)

        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]

        colors = plt.cm.plasma(np.linspace(0, 1, len(cities)))

        ax.scatter(lons, lats, transform=ccrs.PlateCarree(), color=colors,
                   s=120, edgecolors='black', linewidth=1.5, alpha=0.9,
                   zorder=5)

        for i in range(len(cities) - 1):
            ax.plot([lons[i], lons[i+1]], [lats[i], lats[i+1]],
                    transform=ccrs.PlateCarree(),
                    color=plt.cm.plasma(i / (len(cities)-1)), linewidth=3,
                    alpha=0.8, zorder=4, solid_capstyle='round')

        for i, city in enumerate(cities):
            ax.text(lons[i], lats[i] + 0.7, city, transform=ccrs.PlateCarree(),
                    fontsize=11, fontweight='bold', ha='center', va='bottom',
                    bbox=dict(boxstyle="round,pad=0.4",
                              facecolor=plt.cm.plasma(i / len(cities)),
                              alpha=0.9, edgecolor='black'), zorder=6)

        ax.set_title('Маршрут по городам', fontsize=16, fontweight='bold',
                     pad=20)
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()


db = DB_Map(DATABASE)
db.create_user_table()


def seed_cities():
    sample_cities = [
        ("Москва", 55.7558, 37.6176),
        ("Санкт-Петербург", 59.9343, 30.3351),
        ("Казань", 55.7964, 49.1088),
        ("Екатеринбург", 56.8380, 60.5975),
    ]
    conn = db._get_conn()
    with conn:
        cursor = conn.cursor()
        for name, lat, lng in sample_cities:
            try:
                cursor.execute("""INSERT INTO cities (city, lat, lng)
                               VALUES (?, ?, ?)""", (name, lat, lng))
            except sqlite3.IntegrityError:
                pass
        conn.commit()


seed_cities()


@app.route("/")
def index():
    user_id = 1
    cities = db.select_cities(user_id)
    return render_template("index.html", cities=cities, user_id=user_id)


@app.route("/add", methods=["POST"])
def add_city():
    user_id = int(request.form.get("user_id", 1))
    city_name = request.form.get("city_name", "").strip()
    if not city_name:
        flash("Введите название города", "error")
        return redirect(url_for("index"))
    added = db.add_city(user_id, city_name)
    if added:
        flash(f"Город {city_name} добавлен", "success")
    else:
        flash("Город не найден или не удалось добавить", "error")
    return redirect(url_for("index"))


@app.route("/remove", methods=["POST"])
def remove_city():
    user_id = int(request.form.get("user_id", 1))
    city_name = request.form.get("city_name", "").strip()
    if not city_name:
        flash("Не указано название города", "error")
        return redirect(url_for("index"))

    removed = db.remove_city(user_id, city_name)
    if removed:
        flash(f"Город {city_name} удалён из вашего списка", "success")
    else:
        flash("Город не найден или не удалось удалить", "error")

    return redirect(url_for("index"))


@app.route("/map")
def map_page():
    user_id = int(request.args.get("user_id", 1))
    cities = db.select_cities(user_id)
    img_path = "static/img/map.png"
    db.create_graph(img_path, cities)
    distance_total = 0
    for i in range(len(cities) - 1):
        d = db.draw_distance(cities[i], cities[i+1])
        if d is not None:
            distance_total += d
    return render_template("map.html", cities=cities,
                           distance_total=distance_total, img_path=img_path)


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(debug=True)
