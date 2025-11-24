"""
Cliente API - Comunicación con servidor Flask
"""
import requests
import json
import os
from datetime import datetime

class APIClient:
    def __init__(self, base_url=None):
        # URL del servidor (puede venir de variable de entorno)
        self.base_url = base_url or os.getenv('API_URL', 'http://localhost:5000/api')
        self.timeout = 5
        self.session_id = None
        self.cache_file = "puntuaciones_temp.json"
        print(f"🔧 API Client inicializado con URL: {self.base_url}")
    
    def _hacer_peticion(self, endpoint, metodo="GET", datos=None):
        """
        Realizar petición HTTP con manejo de errores
        """
        try:
            url = f"{self.base_url}/{endpoint}"
            
            if metodo == "POST":
                response = requests.post(url, json=datos, timeout=self.timeout)
            else:
                response = requests.get(url, timeout=self.timeout)
            
            # Verificar status code
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.ConnectionError:
            print(f"❌ Error de conexión: No se puede conectar al servidor {self.base_url}")
            return {'error': True, 'mensaje': 'Sin conexión al servidor'}
        
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout: El servidor tardó demasiado en responder")
            return {'error': True, 'mensaje': 'Timeout del servidor'}
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ Error HTTP {e.response.status_code}: {e}")
            return {'error': True, 'mensaje': f'Error del servidor: {e.response.status_code}'}
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error en petición: {e}")
            return {'error': True, 'mensaje': 'Error en la petición'}
        
        except json.JSONDecodeError:
            print("❌ Error: Respuesta del servidor no es JSON válido")
            return {'error': True, 'mensaje': 'Respuesta inválida del servidor'}
    
    def _reintentar_peticion(self, endpoint, metodo="GET", datos=None, intentos=3):
        """
        Reintentar petición en caso de fallo
        """
        for intento in range(intentos):
            resultado = self._hacer_peticion(endpoint, metodo, datos)
            
            if not resultado.get('error'):
                return resultado
            
            print(f"🔄 Reintentando... ({intento + 1}/{intentos})")
        
        # Si todos los intentos fallan, guardar en cache local
        if metodo == "POST" and endpoint == "guardar_puntuacion":
            self._guardar_local(datos)
        
        return resultado
    
    def _guardar_local(self, datos):
        """
        Guardar puntuación localmente cuando falla la conexión
        """
        try:
            puntuacion = {
                'nombre': datos.get('nombre'),
                'puntos': datos.get('puntos'),
                'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sincronizado': False
            }
            
            # Leer cache existente
            cache = []
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
            
            # Añadir nueva puntuación
            cache.append(puntuacion)
            
            # Guardar cache
            with open(self.cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
            
            print(f"💾 Puntuación guardada localmente (sin conexión)")
        
        except Exception as e:
            print(f"❌ Error al guardar localmente: {e}")
    
    def sincronizar_cache(self):
        """
        Sincronizar puntuaciones guardadas localmente con el servidor
        """
        if not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            
            # Intentar sincronizar cada puntuación
            sincronizadas = []
            for puntuacion in cache:
                if not puntuacion.get('sincronizado'):
                    resultado = self._hacer_peticion('guardar_puntuacion', 'POST', {
                        'nombre': puntuacion['nombre'],
                        'puntos': puntuacion['puntos']
                    })
                    
                    if not resultado.get('error'):
                        puntuacion['sincronizado'] = True
                        sincronizadas.append(puntuacion)
            
            # Actualizar cache
            if sincronizadas:
                cache_actualizado = [p for p in cache if not p.get('sincronizado')]
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_actualizado, f, indent=2)
                
                print(f"✅ {len(sincronizadas)} puntuaciones sincronizadas")
        
        except Exception as e:
            print(f"❌ Error al sincronizar cache: {e}")
    
      # ========== ENDPOINTS DEL JUEGO ==========
    
    def iniciar_juego(self, nombre):
        """
        POST /api/iniciar_juego
        Iniciar nueva partida
        """
        datos = {'nombre': nombre}
        resultado = self._reintentar_peticion('iniciar_juego', 'POST', datos)
    
        if not resultado.get('error'):
            self.session_id = resultado.get('session_id')
    
            return resultado

    def disparar(self, objetivo):
        """
        POST /api/disparar
        Realizar disparo
        """
        if not self.session_id:
            return {'error': True, 'mensaje': 'Sin sesión activa'}
        
        datos = {
            'session_id': self.session_id,
            'objetivo': objetivo
        }
        return self._reintentar_peticion('disparar', 'POST', datos)
    
    def turno_bot(self):
        """
        POST /api/turno_bot
        Ejecutar turno del bot
        """
        if not self.session_id:
            return {'error': True, 'mensaje': 'Sin sesión activa'}
        
        datos = {'session_id': self.session_id}
        return self._reintentar_peticion('turno_bot', 'POST', datos)
    
    def obtener_ranking(self, limite=10):
        """
        GET /api/ranking
        Obtener ranking global
        """
        return self._reintentar_peticion(f'ranking?limite={limite}', 'GET')
    
    def obtener_estadisticas(self):
        """
        GET /api/estadisticas
        Obtener estadísticas globales
        """
        return self._reintentar_peticion('estadisticas', 'GET')