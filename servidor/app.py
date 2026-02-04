"""
API REST Flask - Servidor Buckshot Roulette
"""
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from ranking_web import RankingWeb
import logging
from datetime import datetime
import os 
import random 

from config import get_config
from database import init_db
from models import BuckshotGame, Puntuacion, SesionJuego

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear app Flask
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Configurar CORS
CORS(app, resources={
    r"/api/*": {
        "origins": config.CORS_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Inicializar database
try:
    db = init_db(config)
    logger.info("✅ Base de datos conectada correctamente")
    
    # Hacer db disponible para models
    import models
    models.db = db
    
except Exception as e:
    logger.error(f"Error al conectar base de datos: {e}")
    raise

# Inicializar juego
game = BuckshotGame(config)
sesiones = {}


# ============== ENDPOINTS API ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'version': config.API_VERSION
    }), 200


@app.route('/api/iniciar_juego', methods=['POST'])
def iniciar_juego():
    try:
        data = request.get_json()
        nombre = data.get('nombre', 'Jugador')
        session_id = game.generar_session_id()
        escopeta, num_reales, num_fogueo = game.cargar_escopeta()
        sesiones[session_id] = {
            'nombre': nombre,
            'vidas_jugador': config.MAX_VIDAS,
            'vidas_bot': config.MAX_VIDAS,
            'puntos': 0,
            'escopeta': escopeta,
            'turno_jugador': True,
            'balas_disparadas': 0
        }
        SesionJuego.crear(session_id, nombre)
        logger.info(f"Juego iniciado: {nombre} (session: {session_id[:8]}...)")
        return jsonify({
            'error': False,
            'success': True,
            'session_id': session_id,
            'mensaje': f'Escopeta cargada: {num_reales} reales, {num_fogueo} fogueo',
            'vidas_jugador': config.MAX_VIDAS,
            'vidas_bot': config.MAX_VIDAS,
            'puntos': 0,
            'balas_restantes': len(escopeta),
            'turno_jugador': True
        }), 200
    except Exception as e:
        logger.error(f"Error en iniciar_juego: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/disparar', methods=['POST'])
def disparar():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        objetivo = data.get('objetivo')
        
        print("Datos de session_id", session_id)
        print("Datos de objetivo", objetivo)
        print("Datos de sesiones", sesiones.keys())
        
        # Validar sesión
        if session_id not in sesiones:
            return jsonify({'error': True, 'mensaje': 'Sesión inválida'}), 400
        
        sesion = sesiones[session_id]
        
        # Verificar turno
        if not sesion['turno_jugador']:
            return jsonify({
                'error': True,
                'mensaje': 'No es tu turno',
                'turno_jugador': sesion['turno_jugador'],
                'vidas_jugador': sesion['vidas_jugador'],
                'vidas_bot': sesion['vidas_bot'],
                'puntos': sesion['puntos'],
                'balas_restantes': len(sesion.get('escopeta', [])),
                'game_over': False
            }), 200
        
        # Verificar si hay balas
        if not sesion['escopeta']:
            escopeta, num_reales, num_fogueo = game.cargar_escopeta()
            sesion['escopeta'] = escopeta
            
            return jsonify({
                'recarga': True,
                'mensaje': f'NUEVA RONDA: {num_reales} reales, {num_fogueo} fogueo',
                'balas_restantes': len(escopeta),
                'vidas_jugador': sesion['vidas_jugador'],
                'vidas_bot': sesion['vidas_bot'],
                'puntos': sesion['puntos'],
                'turno_jugador': sesion['turno_jugador']
            }), 200
        
        bala = sesion['escopeta'].pop(0)
        sesion['balas_disparadas'] += 1
        
        resultado = game.procesar_disparo(bala, objetivo, True)
        
        if objetivo == 'bot' and resultado['dano'] > 0:
            sesion['vidas_bot'] -= resultado['dano']
        elif objetivo == 'jugador' and resultado['dano'] > 0:
            sesion['vidas_jugador'] -= resultado['dano']
        
        sesion['puntos'] += resultado['puntos_ganados']
        
        if resultado['cambiar_turno']:
            sesion['turno_jugador'] = False
        
        game_over = sesion['vidas_jugador'] <= 0 or sesion['vidas_bot'] <= 0
        
        if game_over:
            Puntuacion.guardar(sesion['nombre'], sesion['puntos'], session_id)
            SesionJuego.finalizar(session_id, sesion['puntos'], sesion['balas_disparadas'])
            del sesiones[session_id]
            
            if sesion['vidas_bot'] <= 0:
                resultado['mensaje'] = "¡VICTORIA! Derrotaste al bot"
        
        return jsonify({
            'success': True,
            'mensaje': resultado['mensaje'],
            'vidas_jugador': sesion.get('vidas_jugador', 0),
            'vidas_bot': sesion.get('vidas_bot', 0),
            'puntos': sesion.get('puntos', 0),
            'balas_restantes': len(sesion.get('escopeta', [])),
            'cambiar_turno': resultado['cambiar_turno'],
            'turno_jugador': sesion.get('turno_jugador', True),
            'game_over': game_over
        }), 200
    
    except Exception as e:
        logger.error(f"Error en disparar: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/turno_bot', methods=['POST'])
def turno_bot():
    """
    POST /api/turno_bot
    Body: {"session_id": "..."}
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        # Validar sesión
        if session_id not in sesiones:
            return jsonify({'error': True, 'mensaje': 'Sesión inválida'}), 400
        
        sesion = sesiones[session_id]
        
        # Verificar si hay balas
        if not sesion['escopeta']:
            escopeta, num_reales, num_fogueo = game.cargar_escopeta()
            sesion['escopeta'] = escopeta
            
            return jsonify({
                'recarga': True,
                'mensaje': f'NUEVA RONDA: {num_reales} reales, {num_fogueo} fogueo',
                'balas_restantes': len(escopeta),
                'vidas_jugador': sesion['vidas_jugador'],
                'vidas_bot': sesion['vidas_bot'],
                'puntos': sesion['puntos'],
                'turno_jugador': sesion['turno_jugador']
            }), 200
        
        # Extraer bala
        bala = sesion['escopeta'].pop(0)
        sesion['balas_disparadas'] += 1
        
        # Bot decide
        objetivo = 'jugador' if random.random() < 0.7 else 'bot'
        
        # Procesar disparo del bot
        if objetivo == 'jugador':
            if bala == 1:
                sesion['vidas_jugador'] -= 1
                mensaje = "El bot te disparó con bala REAL"
            else:
                mensaje = "El bot te disparó - Fogueo"
            cambiar_turno = True
        else:
            if bala == 1:
                sesion['vidas_bot'] -= 1
                mensaje = "El bot se disparó con bala REAL"
            else:
                mensaje = "El bot se disparó - Fogueo, sigue jugando"
            cambiar_turno = False
        
        if cambiar_turno:
            sesion['turno_jugador'] = True
        
        # Verificar game over
        game_over = sesion['vidas_jugador'] <= 0 or sesion['vidas_bot'] <= 0
        
        if game_over:
            Puntuacion.guardar(sesion['nombre'], sesion['puntos'], session_id)
            SesionJuego.finalizar(session_id, sesion['puntos'], sesion['balas_disparadas'])
            del sesiones[session_id]
            
            if sesion['vidas_bot'] <= 0:
                mensaje = "¡VICTORIA! Derrotaste al bot"
        
        return jsonify({
            'success': True,
            'mensaje': mensaje,
            'vidas_jugador': sesion.get('vidas_jugador', 0),
            'vidas_bot': sesion.get('vidas_bot', 0),
            'puntos': sesion.get('puntos', 0),
            'balas_restantes': len(sesion.get('escopeta', [])),
            'cambiar_turno': cambiar_turno,
            'turno_jugador': sesion.get('turno_jugador', True),
            'game_over': game_over
        }), 200
    
    except Exception as e:
        logger.error(f"Error en turno_bot: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/ranking', methods=['GET'])
def obtener_ranking():
    """
    GET /api/ranking?limite=10
    """
    try:
        limite = request.args.get('limite', 10, type=int)
        limite = min(limite, 100)
        
        ranking = Puntuacion.obtener_ranking(limite)
        
        return jsonify({
            'success': True,
            'ranking': ranking,
            'total': len(ranking)
        }), 200
    
    except Exception as e:
        logger.error(f"Error en obtener_ranking: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/estadisticas', methods=['GET'])
def obtener_estadisticas():
    """GET /api/estadisticas"""
    try:
        stats = Puntuacion.obtener_estadisticas()
        return jsonify({
            'success': True,
            'estadisticas': stats
        }), 200
    
    except Exception as e:
        logger.error(f"Error en obtener_estadisticas: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500

# ============== PÁGINA WEB RANKING ==============

@app.route('/')
def index():
    return render_template_string(RankingWeb.get_html())

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': True, 'mensaje': 'Endpoint no encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': True, 'mensaje': 'Error interno del servidor'}), 500


# ============== SHUTDOWN ==============

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Cerrar conexiones al finalizar"""
    pass


if __name__ == '__main__':
    import random  # Necesario para turno_bot
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
