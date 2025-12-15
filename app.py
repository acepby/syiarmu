import os
import threading
import pandas as pd
from flask import Flask
from sqlalchemy.pool import NullPool
from extensions import db
from models import Organization
from routes import main as main_blueprint
from scraper import worker_loop

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'muhammadiyah_monitor_safe.db')

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'super-secret-key'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': NullPool, 'connect_args': {'timeout': 30}}

    db.init_app(app)
    app.register_blueprint(main_blueprint)
    
    return app

def seed_db(app):
    with app.app_context():
        db.create_all()
        coords = {
            "Aceh": (4.6951, 96.7494), "Sumatera Utara": (2.1154, 99.5451), "Sumatera Barat": (-0.7399, 100.8000), "Riau": (0.2933, 101.6959), "Kepulauan Riau": (3.9164, 108.1333), "Jambi": (-1.4852, 102.4381), "Sumatera Selatan": (-3.3194, 104.9145), "Bangka Belitung": (-2.7411, 106.4406), "Bengkulu": (-3.5778, 102.3464), "Lampung": (-4.5586, 105.4068), "DKI Jakarta": (-6.2088, 106.8456), "Banten": (-6.4058, 106.0640), "Jawa Barat": (-6.9175, 107.6191), "Jawa Tengah": (-7.1510, 110.1403), "Yogyakarta": (-7.7956, 110.3695), "Jawa Timur": (-7.5360, 112.2384), "Bali": (-8.3405, 115.0920), "Nusa Tenggara Barat": (-8.6529, 117.3616), "Nusa Tenggara Timur": (-8.6574, 121.0794), "Kalimantan Barat": (-0.2787, 111.4753), "Kalimantan Tengah": (-1.6815, 113.3824), "Kalimantan Selatan": (-3.0926, 115.2838), "Kalimantan Timur": (0.5387, 116.4194), "Kalimantan Utara": (2.9042, 116.3575), "Sulawesi Utara": (0.6247, 123.9750), "Gorontalo": (0.6999, 122.4467), "Sulawesi Tengah": (-1.4300, 121.4456), "Sulawesi Barat": (-2.8441, 119.2321), "Sulawesi Selatan": (-3.6687, 119.9740), "Sulawesi Tenggara": (-4.1449, 122.1746), "Maluku": (-3.2385, 130.1453), "Maluku Utara": (1.5709, 127.8087), "Papua Barat": (-1.3361, 133.1747), "Papua": (-4.2699, 138.0804), "Papua Tengah": (-3.7706, 136.3634), "Papua Pegunungan": (-4.0766, 139.3634), "Papua Selatan": (-7.0000, 139.5000), "Papua Barat Daya": (-1.0000, 131.5000)
        }
        try:
            possible_files = ["data_muhammadiyah.xlsx - Sheet1.csv", "data_muhammadiyah.csv"]
            fname = next((f for f in possible_files if os.path.exists(f)), None)
            if fname:
                df = pd.read_csv(fname)
                for _, r in df.iterrows():
                    if pd.notna(r['PIMPINAN WILAYAH']):
                        name = r['PIMPINAN WILAYAH']
                        if not Organization.query.filter_by(name=name).first():
                            ig = r['LINK INSTAGRAM'] if 'instagram.com' in str(r['LINK INSTAGRAM']) else None
                            web = r['LINK WEBSITE'] if 'http' in str(r['LINK WEBSITE']) else None
                            lat, lng = None, None
                            for key, val in coords.items():
                                if key in name: lat, lng = val; break
                            db.session.add(Organization(name=name, instagram_link=ig, website_link=web, latitude=lat, longitude=lng))
                db.session.commit()
                print("✅ DB Seeded.")
        except Exception as e: print(f"Seed Error: {e}")

if __name__ == '__main__':
    app = create_app()
    seed_db(app)
    if not any(t.name == "SafeWorker" for t in threading.enumerate()):
        threading.Thread(target=worker_loop, args=(app,), name="SafeWorker", daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)