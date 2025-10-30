from flask import Flask, render_template, request, jsonify, session
import sqlite3
import random
from datetime import datetime
import secrets
from pyngrok import ngrok

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

class BuckshotGame:
    def __init__(self):
        self.inicializar_base_datos()
    
    def inicializar_base_datos(self):
        conexion = sqlite3.connect("buckshot_scores.db")
        cursor = conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS puntuaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                puntos INTEGER NOT NULL,
                fecha TEXT NOT NULL
            )
        """)
        conexion.commit()
        conexion.close()
    
    def cargar_escopeta(self):
        num_reales = random.randint(1, 4)
        num_fogueo = random.randint(1, 4)
        escopeta = [1] * num_reales + [0] * num_fogueo
        random.shuffle(escopeta)
        return escopeta, num_reales, num_fogueo
    
    def guardar_puntuacion(self, nombre, puntos):
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conexion = sqlite3.connect("buckshot_scores.db")
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO puntuaciones (nombre, puntos, fecha) VALUES (?, ?, ?)",
            (nombre, puntos, fecha)
        )
        conexion.commit()
        conexion.close()
    
    def obtener_ranking(self, limite=10):
        conexion = sqlite3.connect("buckshot_scores.db")
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT nombre, puntos, fecha 
            FROM puntuaciones 
            ORDER BY puntos DESC 
            LIMIT ?
        """, (limite,))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados

game = BuckshotGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/iniciar_juego', methods=['POST'])
def iniciar_juego():
    data = request.get_json()
    nombre = data.get('nombre', 'Jugador')
    
    escopeta, num_reales, num_fogueo = game.cargar_escopeta()
    
    session['nombre'] = nombre
    session['vidas_jugador'] = 3
    session['vidas_bot'] = 3
    session['puntos'] = 0
    session['escopeta'] = escopeta
    session['turno_jugador'] = True
    
    return jsonify({
        'success': True,
        'mensaje': f'Escopeta cargada: {num_reales} reales, {num_fogueo} fogueo',
        'vidas_jugador': 3,
        'vidas_bot': 3,
        'puntos': 0,
        'balas_restantes': len(escopeta)
    })

@app.route('/disparar', methods=['POST'])
def disparar():
    data = request.get_json()
    objetivo = data.get('objetivo')  # 'jugador' o 'bot'
    
    escopeta = session.get('escopeta', [])
    vidas_jugador = session.get('vidas_jugador', 3)
    vidas_bot = session.get('vidas_bot', 3)
    puntos = session.get('puntos', 0)
    turno_jugador = session.get('turno_jugador', True)
    
    if not escopeta:
        # Recargar escopeta
        escopeta, num_reales, num_fogueo = game.cargar_escopeta()
        session['escopeta'] = escopeta
        return jsonify({
            'recarga': True,
            'mensaje': f'Nueva ronda: {num_reales} reales, {num_fogueo} fogueo',
            'balas_restantes': len(escopeta)
        })
    
    # Extraer bala
    bala = escopeta.pop(0)
    session['escopeta'] = escopeta
    
    cambiar_turno = False
    mensaje = ""
    
    if turno_jugador:
        if objetivo == 'bot':
            if bala == 1:
                vidas_bot -= 1
                puntos += 10
                mensaje = "💥 ¡BANG! Bala REAL al bot (+10 puntos)"
                cambiar_turno = True
            else:
                mensaje = "✨ Click - Fogueo al bot"
                cambiar_turno = True
        else:  # jugador se dispara a sí mismo
            if bala == 1:
                vidas_jugador -= 1
                mensaje = "💀 ¡BANG! Te disparaste con bala REAL"
                cambiar_turno = True
            else:
                puntos += 5
                mensaje = "🎲 Fogueo - Sigues jugando (+5 puntos)"
                cambiar_turno = False
    
    session['vidas_jugador'] = vidas_jugador
    session['vidas_bot'] = vidas_bot
    session['puntos'] = puntos
    session['turno_jugador'] = not cambiar_turno if cambiar_turno else turno_jugador
    
    game_over = vidas_jugador <= 0
    
    if game_over:
        game.guardar_puntuacion(session.get('nombre'), puntos)
    
    return jsonify({
        'success': True,
        'mensaje': mensaje,
        'vidas_jugador': vidas_jugador,
        'vidas_bot': vidas_bot,
        'puntos': puntos,
        'balas_restantes': len(escopeta),
        'cambiar_turno': cambiar_turno,
        'game_over': game_over
    })

@app.route('/turno_bot', methods=['POST'])
def turno_bot():
    escopeta = session.get('escopeta', [])
    vidas_jugador = session.get('vidas_jugador', 3)
    vidas_bot = session.get('vidas_bot', 3)
    puntos = session.get('puntos', 0)
    
    if not escopeta:
        escopeta, num_reales, num_fogueo = game.cargar_escopeta()
        session['escopeta'] = escopeta
        return jsonify({
            'recarga': True,
            'mensaje': f'Nueva ronda: {num_reales} reales, {num_fogueo} fogueo',
            'balas_restantes': len(escopeta)
        })
    
    bala = escopeta.pop(0)
    session['escopeta'] = escopeta
    
    # Bot decide: 70% disparar al jugador
    if random.random() < 0.7:
        objetivo = "jugador"
        if bala == 1:
            vidas_jugador -= 1
            mensaje = "🤖 El bot te disparó con bala REAL"
        else:
            mensaje = "🤖 El bot te disparó - Fogueo"
        cambiar_turno = True
    else:
        objetivo = "bot"
        if bala == 1:
            vidas_bot -= 1
            mensaje = "🤖 El bot se disparó con bala REAL"
        else:
            mensaje = "🤖 El bot se disparó - Fogueo, sigue jugando"
            cambiar_turno = False
    
    session['vidas_jugador'] = vidas_jugador
    session['vidas_bot'] = vidas_bot
    session['turno_jugador'] = cambiar_turno
    
    game_over = vidas_jugador <= 0
    
    if game_over:
        game.guardar_puntuacion(session.get('nombre'), puntos)
    
    return jsonify({
        'success': True,
        'mensaje': mensaje,
        'vidas_jugador': vidas_jugador,
        'vidas_bot': vidas_bot,
        'puntos': puntos,
        'balas_restantes': len(escopeta),
        'cambiar_turno': cambiar_turno,
        'game_over': game_over
    })

@app.route('/ranking')
def ranking():
    resultados = game.obtener_ranking()
    return jsonify({'ranking': resultados})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

    if __name__ == '__main__':
    # Configura tu token de ngrok
    ngrok.set_auth_token("TU_TOKEN_AQUI")
    
    # Crea el túnel público
    public_url = ngrok.connect(5000)
    print("\n" + "="*60)
    print("🌐 SERVIDOR PÚBLICO ACTIVO")
    print("="*60)
    print(f"URL Local:   http://localhost:5000")
    print(f"URL Pública: {public_url}")
    print("="*60 + "\n")
    print("Comparte la URL pública con tus amigos para que jueguen\n")
    
    # Inicia Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
