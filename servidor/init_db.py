"""
Script para inicializar la base de datos PostgreSQL
Crea las tablas necesarias y verifica la conexión
"""
import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar configuración y database
from config import get_config
from database import init_db

def main():
    """Inicializar base de datos"""
    print("="*60)
    print("INICIALIZANDO BASE DE DATOS - Buckshot Roulette")
    print("="*60)
    
    try:
        # Obtener configuración
        config = get_config()
        print(f"\nConfiguración: {config.__class__.__name__}")
        print(f"Base de datos: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else 'local'}")
        
        # Inicializar database
        print("\nConectando a PostgreSQL...")
        db = init_db(config)
        
        print("\nBase de datos inicializada correctamente")
        print("\nTablas creadas:")
        print("   - puntuaciones (id, nombre, puntos, fecha, session_id)")
        print("   - sesiones_juego (id, session_id, nombre_jugador, fecha_inicio, fecha_fin, puntos_finales, balas_disparadas)")
        
        print("\nÍndices creados:")
        print("   - idx_puntuaciones_puntos (para ranking)")
        print("   - idx_puntuaciones_fecha (para filtros por fecha)")
        
        # Verificar que se puede hacer una consulta
        print("\nProbando consulta...")
        with db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM puntuaciones")
            count = cursor.fetchone()[0]
            print(f"   Total de puntuaciones: {count}")
        
        print("\n" + "="*60)
        print("TODO LISTO - Puedes ejecutar el servidor con:")
        print("   python app.py")
        print("="*60 + "\n")
        
        # Cerrar conexiones
        db.close_all_connections()
        
    except Exception as e:
        print(f"\nERROR al inicializar base de datos:")
        print(f"   {type(e).__name__}: {e}")
        print("\nVerifica que:")
        print("   1. PostgreSQL está corriendo: sudo systemctl status postgresql")
        print("   2. Las credenciales en .env son correctas")
        print("   3. La base de datos existe: sudo -u postgres psql -c '\\l'")
        sys.exit(1)

if __name__ == "__main__":
    main()
