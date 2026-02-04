"""
Manejo de conexión a PostgreSQL con connection pooling
"""
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class Database:
    """Clase para manejar conexiones PostgreSQL con pool"""
    
    def __init__(self, config):
        self.config = config
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializar connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                self.config.DB_POOL_MIN,
                self.config.DB_POOL_MAX,
                self.config.DATABASE_URL
            )
            
            if self.connection_pool:
                logger.info(f"Connection pool creado: {self.config.DB_POOL_MIN}-{self.config.DB_POOL_MAX} conexiones")
            else:
                raise Exception("No se pudo crear el connection pool")
        
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f"Error al crear connection pool: {error}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obtener conexión del pool
        Uso:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                ...
        """
        connection = None
        try:
            connection = self.connection_pool.getconn()
            yield connection
            connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Error en transacción: {e}")
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """
        Context manager para obtener cursor directamente
        Uso:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM tabla")
        """
        with self.get_connection() as connection:
            cursor = connection.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute_query(self, query, params=None, fetch=False):
        """
        Ejecutar query simple
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            
            if fetch:
                return cursor.fetchall()
            return cursor.rowcount
    
    def execute_one(self, query, params=None):
        """
        Ejecutar query y obtener un solo resultado
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def execute_many(self, query, params_list):
        """
        Ejecutar query múltiple (bulk insert/update)
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def close_all_connections(self):
        """Cerrar todas las conexiones del pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("🔒 Todas las conexiones cerradas")
    
    def initialize_database(self):
        """Crear tablas necesarias"""
        with self.get_cursor() as cursor:
            # Tabla de puntuaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS puntuaciones (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    puntos INTEGER NOT NULL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id VARCHAR(100),
                    CONSTRAINT puntos_positivos CHECK (puntos >= 0)
                )
            """)
            
            # Índices para optimizar consultas
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_puntuaciones_puntos 
                ON puntuaciones(puntos DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_puntuaciones_fecha 
                ON puntuaciones(fecha DESC)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sesiones_juego (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    nombre_jugador VARCHAR(100) NOT NULL,
                    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_fin TIMESTAMP,
                    puntos_finales INTEGER,
                    balas_disparadas INTEGER DEFAULT 0,
                    CONSTRAINT session_id_valido CHECK (session_id != '')
                )
            """)
            
            logger.info("Base de datos inicializada correctamente")


# Instancia global (se inicializa en app.py)
db = None


def init_db(config):
    """Inicializar database con configuración"""
    global db
    db = Database(config)
    db.initialize_database()
    return db
