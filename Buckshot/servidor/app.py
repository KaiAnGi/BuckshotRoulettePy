"""
API REST Flask - Servidor Buckshot Roulette
"""
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
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
    logger.error(f"❌ Error al conectar base de datos: {e}")
    raise

# Inicializar juego
game = BuckshotGame(config)

# Almacenamiento temporal de sesiones (en producción usar Redis)
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
    """
    POST /api/iniciar_juego
    Body: {"nombre": "Jugador"}
    """
    try:
        data = request.get_json()
        nombre = data.get('nombre', 'Jugador')
        
        # Generar sesión
        session_id = game.generar_session_id()
        
        # Cargar escopeta
        escopeta, num_reales, num_fogueo = game.cargar_escopeta()
        
        # Guardar sesión
        sesiones[session_id] = {
            'nombre': nombre,
            'vidas_jugador': config.MAX_VIDAS,
            'vidas_bot': config.MAX_VIDAS,
            'puntos': 0,
            'escopeta': escopeta,
            'turno_jugador': True,
            'balas_disparadas': 0
        }
        
        # Registrar en BD
        SesionJuego.crear(session_id, nombre)
        
        logger.info(f"🎮 Juego iniciado: {nombre} (session: {session_id[:8]}...)")
        
        return jsonify({
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
        logger.error(f"❌ Error en iniciar_juego: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/disparar', methods=['POST'])
def disparar():
    """
    POST /api/disparar
    Body: {"session_id": "...", "objetivo": "bot" | "jugador"}
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        objetivo = data.get('objetivo')
        
        # Validar sesión
        if session_id not in sesiones:
            return jsonify({'error': True, 'mensaje': 'Sesión inválida'}), 400
        
        sesion = sesiones[session_id]
        
        # Verificar turno
        if not sesion['turno_jugador']:
            return jsonify({'error': True, 'mensaje': 'No es tu turno'}), 400
        
        # Verificar si hay balas
        if not sesion['escopeta']:
            # Recargar escopeta
            escopeta, num_reales, num_fogueo = game.cargar_escopeta()
            sesion['escopeta'] = escopeta
            
            return jsonify({
                'recarga': True,
                'mensaje': f'🔄 Nueva ronda: {num_reales} reales, {num_fogueo} fogueo',
                'balas_restantes': len(escopeta),
                'vidas_jugador': sesion['vidas_jugador'],
                'vidas_bot': sesion['vidas_bot'],
                'puntos': sesion['puntos'],
                'turno_jugador': sesion['turno_jugador']
            }), 200
        
        # Extraer bala
        bala = sesion['escopeta'].pop(0)
        sesion['balas_disparadas'] += 1
        
        # Procesar disparo
        resultado = game.procesar_disparo(bala, objetivo, True)
        
        # Actualizar estado
        if objetivo == 'bot' and resultado['dano'] > 0:
            sesion['vidas_bot'] -= resultado['dano']
        elif objetivo == 'jugador' and resultado['dano'] > 0:
            sesion['vidas_jugador'] -= resultado['dano']
        
        sesion['puntos'] += resultado['puntos_ganados']
        
        if resultado['cambiar_turno']:
            sesion['turno_jugador'] = False
        
        # Verificar game over
        game_over = sesion['vidas_jugador'] <= 0 or sesion['vidas_bot'] <= 0
        
        # Preparar respuesta ANTES de borrar sesión
        respuesta = {
            'success': True,
            'mensaje': resultado['mensaje'],
            'vidas_jugador': sesion['vidas_jugador'],
            'vidas_bot': sesion['vidas_bot'],
            'puntos': sesion['puntos'],
            'balas_restantes': len(sesion['escopeta']),
            'cambiar_turno': resultado['cambiar_turno'],
            'turno_jugador': sesion['turno_jugador'],
            'game_over': game_over
        }
        
        if game_over:
            Puntuacion.guardar(sesion['nombre'], sesion['puntos'], session_id)
            SesionJuego.finalizar(session_id, sesion['puntos'], sesion['balas_disparadas'])
            
            if sesion['vidas_bot'] <= 0:
                respuesta['mensaje'] = "🎉 ¡VICTORIA! Derrotaste al bot"
            
            del sesiones[session_id]
        
        return jsonify(respuesta), 200
    
    except Exception as e:
        logger.error(f"❌ Error en disparar: {e}")
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
                'mensaje': f'🔄 Nueva ronda: {num_reales} reales, {num_fogueo} fogueo',
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
                mensaje = "🤖 El bot te disparó con bala REAL"
            else:
                mensaje = "🤖 El bot te disparó - Fogueo"
            cambiar_turno = True
        else:
            if bala == 1:
                sesion['vidas_bot'] -= 1
                mensaje = "🤖 El bot se disparó con bala REAL"
            else:
                mensaje = "🤖 El bot se disparó - Fogueo, sigue jugando"
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
                mensaje = "🎉 ¡VICTORIA! Derrotaste al bot"
        
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
        logger.error(f"❌ Error en turno_bot: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


@app.route('/api/ranking', methods=['GET'])
def obtener_ranking():
    """
    GET /api/ranking?limite=10
    """
    try:
        limite = request.args.get('limite', 10, type=int)
        limite = min(limite, 100)  # Máximo 100
        
        ranking = Puntuacion.obtener_ranking(limite)
        
        return jsonify({
            'success': True,
            'ranking': ranking,
            'total': len(ranking)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error en obtener_ranking: {e}")
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
        logger.error(f"❌ Error en obtener_estadisticas: {e}")
        return jsonify({'error': True, 'mensaje': str(e)}), 500


# ============== PÁGINA WEB RANKING ==============

@app.route('/')
def index():
    """Página web simple para mostrar ranking"""
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎰 Buckshot Roulette - Ranking Global</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Arial', sans-serif;
                background: linear-gradient(135deg, #1e1e1e 0%, #3a0000 100%);
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(0, 0, 0, 0.7);
                border: 3px solid #ff0000;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 0 30px rgba(255, 0, 0, 0.5);
            }
            h1 {
                text-align: center;
                color: #ff0000;
                margin-bottom: 30px;
                text-shadow: 2px 2px 5px #000;
                font-size: 2.5em;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-bottom: 30px;
            }
            .stat-box {
                background: #2a2a2a;
                border: 2px solid #ff0000;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
            }
            .stat-label { font-size: 14px; color: #aaa; }
            .stat-value { font-size: 24px; font-weight: bold; color: #ff0000; margin-top: 5px; }
            .ranking-item {
                padding: 15px;
                margin: 10px 0;
                background: #2a2a2a;
                border-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: transform 0.2s;
            }
            .ranking-item:hover { transform: translateX(5px); }
            .ranking-item.top3 { border-left: 5px solid #ffd700; }
            .ranking-pos { font-size: 24px; font-weight: bold; margin-right: 15px; }
            .ranking-nombre { flex: 1; font-size: 18px; }
            .ranking-puntos { font-size: 20px; color: #ff0000; font-weight: bold; }
            .ranking-fecha { font-size: 12px; color: #888; margin-left: 10px; }
            .loading { text-align: center; padding: 50px; font-size: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 BUCKSHOT ROULETTE</h1>
            <h2 style="text-align: center; color: #ff0000; margin-bottom: 20px;">🏆 RANKING GLOBAL</h2>
            
            <div class="stats" id="stats">
                <div class="stat-box">
                    <div class="stat-label">Total Partidas</div>
                    <div class="stat-value" id="total-partidas">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Promedio Puntos</div>
                    <div class="stat-value" id="promedio-puntos">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Récord</div>
                    <div class="stat-value" id="max-puntos">-</div>
                </div>
            </div>
            
            <div id="ranking-lista" class="loading">Cargando ranking...</div>
        </div>
        
        <script>
            async function cargarDatos() {
                try {
                    // Cargar ranking
                    const rankingRes = await fetch('/api/ranking?limite=10');
                    const rankingData = await rankingRes.json();
                    
                    // Cargar estadísticas
                    const statsRes = await fetch('/api/estadisticas');
                    const statsData = await statsRes.json();
                    
                    // Mostrar estadísticas
                    if (statsData.estadisticas) {
                        document.getElementById('total-partidas').textContent = statsData.estadisticas.total_partidas;
                        document.getElementById('promedio-puntos').textContent = statsData.estadisticas.promedio_puntos;
                        document.getElementById('max-puntos').textContent = statsData.estadisticas.max_puntos;
                    }
                    
                    // Mostrar ranking
                    const lista = document.getElementById('ranking-lista');
                    if (rankingData.ranking && rankingData.ranking.length > 0) {
                        lista.innerHTML = rankingData.ranking.map((item, index) => {
                            const top3 = index < 3 ? 'top3' : '';
                            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
                            return `
                                <div class="ranking-item ${top3}">
                                    <div class="ranking-pos">${medal} ${index + 1}</div>
                                    <div class="ranking-nombre">${item.nombre}</div>
                                    <div>
                                        <div class="ranking-puntos">${item.puntos} pts</div>
                                        <div class="ranking-fecha">${new Date(item.fecha).toLocaleDateString()}</div>
                                    </div>
                                </div>
                            `;
                        }).join('');
                    } else {
                        lista.innerHTML = '<div class="loading">No hay puntuaciones todavía</div>';
                    }
                    
                } catch (error) {
                    document.getElementById('ranking-lista').innerHTML = 
                        '<div class="loading" style="color: #ff0000;">Error al cargar datos</div>';
                    console.error(error);
                }
            }
            
            cargarDatos();
            setInterval(cargarDatos, 30000); // Actualizar cada 30s
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


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
