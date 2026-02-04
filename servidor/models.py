"""
Modelos de datos y lógica del juego
"""
import random
import secrets
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Inicializar db como None, será asignado por app.py
db = None


class BuckshotGame:
    """Lógica principal del juego Buckshot Roulette"""
    
    def __init__(self, config):
        self.config = config
    
    def cargar_escopeta(self):
        """
        Cargar escopeta con balas aleatorias
        Returns: (escopeta, num_reales, num_fogueo)
        """
        num_reales = random.randint(
            self.config.MIN_BALAS_REALES,
            self.config.MAX_BALAS_REALES
        )
        num_fogueo = random.randint(
            self.config.MIN_BALAS_FOGUEO,
            self.config.MAX_BALAS_FOGUEO
        )
        
        # 1 = real, 0 = fogueo
        escopeta = [1] * num_reales + [0] * num_fogueo
        random.shuffle(escopeta)
        
        return escopeta, num_reales, num_fogueo
    
    def generar_session_id(self):
        """Generar ID único de sesión"""
        return secrets.token_urlsafe(32)
    
    def procesar_disparo(self, bala, objetivo, turno_jugador):
        """
        Procesar resultado de disparo
        Returns: dict con resultado
        """
        resultado = {
            'bala_real': bala == 1,
            'dano': 0,
            'puntos_ganados': 0,
            'cambiar_turno': False,
            'mensaje': ''
        }
        
        if turno_jugador:
            if objetivo == 'bot':
                if bala == 1:
                    resultado['dano'] = 1
                    resultado['puntos_ganados'] = self.config.PUNTOS_BALA_REAL
                    resultado['mensaje'] = "¡BANG! Bala REAL al bot"
                else:
                    resultado['mensaje'] = "Click - Fogueo al bot"
                resultado['cambiar_turno'] = True
            
            else:  # jugador se dispara a sí mismo
                if bala == 1:
                    resultado['dano'] = 1
                    resultado['mensaje'] = "¡BANG! Te disparaste con bala REAL"
                    resultado['cambiar_turno'] = True
                else:
                    resultado['puntos_ganados'] = self.config.PUNTOS_FOGUEO_SELF
                    resultado['mensaje'] = "Fogueo - Sigues jugando"
                    resultado['cambiar_turno'] = False
        
        else:  # turno del bot
            # Bot decide: 70% disparar al jugador, 30% a sí mismo
            if random.random() < 0.7:
                objetivo = 'jugador'
            else:
                objetivo = 'bot'
            
            if objetivo == 'jugador':
                if bala == 1:
                    resultado['dano'] = 1
                    resultado['mensaje'] = "El bot te disparó con bala REAL"
                else:
                    resultado['mensaje'] = "El bot te disparó - Fogueo"
                resultado['cambiar_turno'] = True
            else:
                if bala == 1:
                    resultado['dano'] = -1  # Daño al bot
                    resultado['mensaje'] = "El bot se disparó con bala REAL"
                else:
                    resultado['mensaje'] = "El bot se disparó - Fogueo, sigue"
                    resultado['cambiar_turno'] = False
        
        return resultado


class Puntuacion:
    """Modelo para manejar puntuaciones"""
    
    @staticmethod
    def guardar(nombre, puntos, session_id=None):
        """
        Guardar puntuación en base de datos
        """
        try:
            query = """
                INSERT INTO puntuaciones (nombre, puntos, session_id, fecha)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            params = (nombre, puntos, session_id, datetime.now())
            
            result = db.execute_one(query, params)
            
            if result:
                logger.info(f"Puntuación guardada: {nombre} - {puntos} pts")
                return result[0]
            
            return None
        
        except Exception as e:
            logger.error(f"Error al guardar puntuación: {e}")
            raise
    
    @staticmethod
    def obtener_ranking(limite=10):
        """
        Obtener top puntuaciones
        """
        try:
            query = """
                SELECT nombre, puntos, fecha
                FROM puntuaciones
                ORDER BY puntos DESC, fecha DESC
                LIMIT %s
            """
            
            resultados = db.execute_query(query, (limite,), fetch=True)
            
            # Formatear resultados
            ranking = [
                {
                    'nombre': row[0],
                    'puntos': row[1],
                    'fecha': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None
                }
                for row in resultados
            ]
            
            return ranking
        
        except Exception as e:
            logger.error(f"Error al obtener ranking: {e}")
            raise
    
    @staticmethod
    def obtener_ranking_por_fecha(limite=10, fecha_desde=None):
        """
        Obtener ranking filtrado por fecha
        """
        try:
            if fecha_desde:
                query = """
                    SELECT nombre, puntos, fecha
                    FROM puntuaciones
                    WHERE fecha >= %s
                    ORDER BY puntos DESC, fecha DESC
                    LIMIT %s
                """
                params = (fecha_desde, limite)
            else:
                query = """
                    SELECT nombre, puntos, fecha
                    FROM puntuaciones
                    ORDER BY puntos DESC, fecha DESC
                    LIMIT %s
                """
                params = (limite,)
            
            resultados = db.execute_query(query, params, fetch=True)
            
            ranking = [
                {
                    'nombre': row[0],
                    'puntos': row[1],
                    'fecha': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None
                }
                for row in resultados
            ]
            
            return ranking
        
        except Exception as e:
            logger.error(f"Error al obtener ranking por fecha: {e}")
            raise
    
    @staticmethod
    def obtener_estadisticas():
        """
        Obtener estadísticas globales del juego
        """
        try:
            query = """
                SELECT 
                    COUNT(*) as total_partidas,
                    AVG(puntos) as promedio_puntos,
                    MAX(puntos) as max_puntos,
                    MIN(puntos) as min_puntos
                FROM puntuaciones
            """
            
            resultado = db.execute_one(query)
            
            if resultado:
                return {
                    'total_partidas': resultado[0],
                    'promedio_puntos': round(float(resultado[1]), 2) if resultado[1] else 0,
                    'max_puntos': resultado[2],
                    'min_puntos': resultado[3]
                }
            
            return None
        
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            raise


class SesionJuego:
    """Modelo para manejar sesiones de juego"""
    
    @staticmethod
    def crear(session_id, nombre_jugador):
        """Crear nueva sesión"""
        try:
            query = """
                INSERT INTO sesiones_juego (session_id, nombre_jugador)
                VALUES (%s, %s)
                RETURNING id
            """
            
            result = db.execute_one(query, (session_id, nombre_jugador))
            return result[0] if result else None
        
        except Exception as e:
            logger.error(f"Error al crear sesión: {e}")
            raise
    
    @staticmethod
    def finalizar(session_id, puntos_finales, balas_disparadas):
        """Finalizar sesión"""
        try:
            query = """
                UPDATE sesiones_juego
                SET fecha_fin = %s, puntos_finales = %s, balas_disparadas = %s
                WHERE session_id = %s
            """
            
            db.execute_query(
                query,
                (datetime.now(), puntos_finales, balas_disparadas, session_id)
            )
        
        except Exception as e:
            logger.error(f"Error al finalizar sesión: {e}")
            raise
