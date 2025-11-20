"""
Manejo de conexión a SQLite
"""
import sqlite3
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class Database:
    """Clase para manejar conexiones SQLite"""
    
    def __init__(self, config):
        self.config = config
        # SQLite usa un archivo, no URL compleja
        self.db_file = config.DATABASE_URL.replace('sqlite:///', '')
        self._initialize_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager para obtener conexión"""
        connection = sqlite3.connect(self.db_file)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"❌ Error en transacción: {e}")
            raise
        finally:
            connection.close()
    
    @contextmanager
    def get_cursor(self):
        """Context manager para obtener cursor"""
        with self.get_connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute_query(self, query, params=None, fetch=False):
        """Ejecutar query simple"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or [])
            if fetch:
                return cursor.fetchall()
            return cursor.rowcount
    
    def execute_one(self, query, params=None):
        """Ejecutar query y obtener un resultado"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchone()
    
    def _initialize_database(self):
        """Crear tablas necesarias"""
        with self.get_cursor() as cursor:
            # Tabla de puntuaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS puntuaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    puntos INTEGER NOT NULL CHECK(puntos >= 0),
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT
                )
            """)
            
            # Índices para puntuaciones
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_puntuaciones_puntos 
                ON puntuaciones(puntos DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_puntuaciones_fecha 
                ON puntuaciones(fecha DESC)
            """)
            
            # Tabla de sesiones de juego
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sesiones_juego (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    nombre_jugador TEXT NOT NULL,
                    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_fin TIMESTAMP,
                    puntos_finales INTEGER,
                    balas_disparadas INTEGER DEFAULT 0
                )
            """)
            
            logger.info("✅ Base de datos SQLite inicializada")


# Instancia global
db = None


def init_db(config):
    """Inicializar database"""
    global db
    db = Database(config)
    return db
