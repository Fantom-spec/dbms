import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hospital.db')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
FLASK_API_MODE = os.environ.get('FLASK_API_MODE', 'real')  # 'real' or 'stub'