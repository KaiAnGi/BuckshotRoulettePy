"""
Configuración del servidor - Variables de entorno y settings
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuración base"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///buckshot_roulette.db')    
    # Si usas Heroku/Railway, convierten postgres:// a postgresql://
    # if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    #     DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Connection Pool
    DB_POOL_MIN = int(os.getenv('DB_POOL_MIN', '1'))
    DB_POOL_MAX = int(os.getenv('DB_POOL_MAX', '10'))
    
    # API Settings
    API_TITLE = 'Buckshot Roulette API'
    API_VERSION = '1.0'
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # Game Settings
    MAX_VIDAS = 3
    PUNTOS_BALA_REAL = 10
    PUNTOS_FOGUEO_SELF = 5
    MIN_BALAS_REALES = 1
    MAX_BALAS_REALES = 4
    MIN_BALAS_FOGUEO = 1
    MAX_BALAS_FOGUEO = 4


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///buckshot_roulette_dev.db')


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    # En producción, DATABASE_URL debe venir de variable de entorno
    # if not os.getenv('DATABASE_URL'):
    #     raise ValueError("DATABASE_URL environment variable must be set in production")


class TestingConfig(Config):
    """Configuración para tests"""
    TESTING = True
    DATABASE_URL = 'postgresql://localhost/buckshot_roulette_test'


# Seleccionar configuración según entorno
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Obtener configuración según variable de entorno"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
