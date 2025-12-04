"""
Buckshot Roulette - Cliente Pygame
Main entry point
"""
import pygame
import sys
from pantallas import PantallaInicio, PantallaJuego, PantallaRanking
from api_client import APIClient


class BuckshotRouletteGame:
    def __init__(self):
        pygame.init()
        
        # Configuración de ventana
        self.WIDTH = 800
        self.HEIGHT = 600
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("🎰 Buckshot Roulette")
        
        # Clock para FPS
        self.clock = pygame.time.Clock()
        self.FPS = 60
        
        # Cliente API
        self.api_client = APIClient()
        
        # Estado del juego
        self.pantalla_actual = "inicio"
        self.datos_juego = {}
        self.nombre_jugador = ""
        
        # Inicializar pantallas
        self.pantallas = {
            "inicio": PantallaInicio(self.screen, self.WIDTH, self.HEIGHT),
            "juego": PantallaJuego(self.screen, self.WIDTH, self.HEIGHT),
            "ranking": PantallaRanking(self.screen, self.WIDTH, self.HEIGHT)
        }
        
    def iniciar_juego(self, nombre):
        """Iniciar nueva partida"""
        self.nombre_jugador = nombre
        print(f"🎮 Iniciando juego para: {nombre}")  # ← Añade esto
        resultado = self.api_client.iniciar_juego(nombre)
        
        print(f"📥 Respuesta de iniciar_juego: {resultado}")  # ← Añade esto
        
        if resultado and not resultado.get('error'):
            self.datos_juego = resultado
            self.pantalla_actual = "juego"
            self.pantallas["juego"].actualizar_datos(resultado)
            print(f"✅ Juego iniciado correctamente")  # ← Añade esto
            return True
        else:
            print(f"❌ Error al conectar con servidor: {resultado}")  # ← Añade esto
            return False

    
    def disparar(self, objetivo):
        """Realizar disparo"""
        print(f"🎯 Intentando disparar a: {objetivo}")
        print(f"🔑 Session ID actual: {self.api_client.session_id[:8] if self.api_client.session_id else 'NONE'}")
        
        resultado = self.api_client.disparar(objetivo)
        
        print(f"📥 Respuesta de disparar: {resultado}")
        
        if resultado and not resultado.get('error'):
            self.datos_juego.update(resultado)
            self.pantallas["juego"].actualizar_datos(resultado)
            
            if resultado.get('game_over'):
                self.pantalla_actual = "ranking"
                self.cargar_ranking()
            
            return resultado
        else:
            print(f"❌ Error en disparar: {resultado}")
        return None

    def turno_bot(self):
        """Ejecutar turno del bot"""
        print("🤖 Ejecutando turno del bot...")
        resultado = self.api_client.turno_bot()
        
        if resultado and not resultado.get('error'):
            self.datos_juego.update(resultado)
            self.pantallas["juego"].actualizar_datos(resultado)
            
            if resultado.get('game_over'):
                self.pantalla_actual = "ranking"
                self.cargar_ranking()
            
            return resultado
        return None

    
    def cargar_ranking(self):
        """Cargar ranking global"""
        resultado = self.api_client.obtener_ranking()
        
        if resultado and not resultado.get('error'):
            self.pantallas["ranking"].actualizar_ranking(
                resultado.get('ranking', []),
                self.datos_juego.get('puntos', 0),
                self.nombre_jugador
            )
    
    def cambiar_pantalla(self, nueva_pantalla):
        """Cambiar de pantalla"""
        self.pantalla_actual = nueva_pantalla
        
        if nueva_pantalla == "ranking":
            self.cargar_ranking()
    
    def reiniciar_juego(self):
        """Reiniciar juego completo"""
        self.pantalla_actual = "inicio"
        self.datos_juego = {}
        self.nombre_jugador = ""
    
    def run(self):
        """Loop principal del juego"""
        running = True
        
        while running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
            
            pantalla = self.pantallas[self.pantalla_actual]
            accion = pantalla.render(events)
            
            if accion:
                if accion['tipo'] == 'iniciar_juego':
                    self.iniciar_juego(accion['nombre'])
                
                elif accion['tipo'] == 'disparar':
                    self.disparar(accion['objetivo'])
                
                elif accion['tipo'] == 'turno_bot':
                    self.turno_bot()
                
                elif accion['tipo'] == 'ver_ranking':
                    self.cambiar_pantalla('ranking')
                
                elif accion['tipo'] == 'reiniciar':
                    self.reiniciar_juego()
                
                elif accion['tipo'] == 'salir':
                    running = False
            
            pygame.display.flip()
            self.clock.tick(self.FPS)
        
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = BuckshotRouletteGame()
    game.run()
