"""
Script para probar la conexión a PostgreSQL
Verifica credenciales, conexión y operaciones básicas
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import os
import sys

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def test_connection():
    """Probar conexión a PostgreSQL"""
    print("="*60)
    print("🧪 TEST DE CONEXIÓN - PostgreSQL")
    print("="*60)
    
    if not DATABASE_URL:
        print("\n❌ ERROR: DATABASE_URL no está definida en .env")
        sys.exit(1)
    
    # Ocultar password en el log
    url_parts = DATABASE_URL.split('@')
    safe_url = f"***@{url_parts[1]}" if len(url_parts) > 1 else "***"
    print(f"\n🔗 Conectando a: {safe_url}")
    
    connection = None
    
    try:
        # 1. Probar conexión básica
        print("\n[1/6] 🔌 Probando conexión básica...")
        connection = psycopg2.connect(DATABASE_URL)
        print("      ✅ Conexión exitosa")
        
        # 2. Verificar versión de PostgreSQL
        print("\n[2/6] 📌 Verificando versión de PostgreSQL...")
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        version_short = version.split(',')[0]
        print(f"      ✅ {version_short}")
        
        # 3. Verificar base de datos actual
        print("\n[3/6] 🗄️  Verificando base de datos...")
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"      ✅ Base de datos: {db_name}")
        
        # 4. Probar crear tabla temporal
        print("\n[4/6] 🛠️  Probando crear tabla temporal...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                mensaje TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
        print("      ✅ Tabla creada exitosamente")
        
        # 5. Probar INSERT
        print("\n[5/6] 💾 Probando INSERT...")
        cursor.execute("""
            INSERT INTO test_table (mensaje) 
            VALUES (%s) 
            RETURNING id, mensaje, created_at
        """, ("Test de conexión exitoso",))
        result = cursor.fetchone()
        connection.commit()
        print(f"      ✅ Registro insertado - ID: {result[0]}")
        
        # 6. Probar SELECT
        print("\n[6/6] 📖 Probando SELECT...")
        cursor.execute("SELECT * FROM test_table ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        print(f"      ✅ Datos recuperados: {row[1]}")
        
        # Limpiar tabla de prueba
        print("\n🧹 Limpiando tabla de prueba...")
        cursor.execute("DROP TABLE IF EXISTS test_table")
        connection.commit()
        print("      ✅ Tabla eliminada")
        
        # Cerrar cursor
        cursor.close()
        
        # Test de connection pool
        print("\n🔄 Probando múltiples conexiones...")
        connections = []
        for i in range(3):
            conn = psycopg2.connect(DATABASE_URL)
            connections.append(conn)
            print(f"      ✅ Conexión {i+1}/3 establecida")
        
        # Cerrar conexiones de prueba
        for conn in connections:
            conn.close()
        print("      ✅ Todas las conexiones cerradas")
        
        # Resultado final
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS PASARON CORRECTAMENTE")
        print("="*60)
        print("\n💡 Puedes proceder a:")
        print("   1. Inicializar la BD: python init_db.py")
        print("   2. Ejecutar el servidor: python app.py")
        print("\n")
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ ERROR DE CONEXIÓN:")
        print(f"   {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verificar que PostgreSQL está corriendo:")
        print("      sudo systemctl status postgresql")
        print("   2. Verificar credenciales en .env")
        print("   3. Verificar que la base de datos existe:")
        print("      sudo -u postgres psql -c '\\l'")
        sys.exit(1)
        
    except psycopg2.Error as e:
        print(f"\n❌ ERROR DE POSTGRESQL:")
        print(f"   {type(e).__name__}: {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ ERROR GENERAL:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        # Cerrar conexión principal
        if connection:
            connection.close()
            print("🔒 Conexión cerrada\n")

if __name__ == "__main__":
    test_connection()
