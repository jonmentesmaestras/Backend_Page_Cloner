import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
import pymysql.cursors

app = FastAPI(
    title="Landings System API",
    description="API REST for Landings and Buckets interaction with MariaDB",
    version="1.0.0"
)

# Configuración de CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen (frontend). Para producción ajusta a ej: ["http://localhost:3000", "https://midominio.com"]
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Permite todos los headers
)

# -----------------------------------------------------------------------------
# Esquemas de Datos (Pydantic)
# -----------------------------------------------------------------------------
class LandingCreate(BaseModel):
    FK_ID_Dominios_Usuarios: int
    Nombre: str
    URL: str
    Pixel: str
    Cta_Link: str
    FK_UserID: int
    FK_ID_Bucket_Usuarios: int
    Active: int
    CreatedAt: Optional[datetime] = None
    UpdatedAt: Optional[datetime] = None

# -----------------------------------------------------------------------------
# Gestión de la Base de Datos
# -----------------------------------------------------------------------------
def get_db_connection() -> pymysql.connections.Connection:
    """
    Obtiene una nueva conexión a la base de datos MariaDB.
    Las credenciales son cargadas estrictamente desde variables de entorno
    garantizando la seguridad del despliegue (security-audit).
    """
    try:
        return pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", ""),
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
    except pymysql.MySQLError as e:
        # Se captura el error específico de la DB y no se silencia (code-smells-expert)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al conectar a la base de datos.",
                "details": str(e)
            }
        )

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """
    Verifica que el servidor esté activo y escuchando peticiones.
    """
    return {"status": "ok", "message": "Server is running"}

@app.get("/api/v1/landings-buckets", response_model=List[Dict[str, Any]])
def get_landings_buckets(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Consulta todos los registros disponibles en la vista view_Landings_Buckets.
    Permite filtrar opcionalmente por usuario usando el query param ?user_id=105.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if user_id is not None:
                # Consulta filtrada con parámetro estricto para evitar SQLi (security-audit)
                sql = "SELECT * FROM view_Landings_Buckets WHERE FK_UserID = %s;"
                cursor.execute(sql, (user_id,))
            else:
                # Consulta genérica
                sql = "SELECT * FROM view_Landings_Buckets;"
                cursor.execute(sql)
                
            results: List[Dict[str, Any]] = cursor.fetchall()
            return results
    except pymysql.MySQLError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al consultar la vista de landings y buckets.",
                "details": str(e)
            }
        )
    finally:
        connection.close()

@app.post("/api/v1/landings")
def create_landing(landing: LandingCreate) -> Dict[str, Any]:
    """
    Inserta una nueva fila en la tabla Landings_Usuarios.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Configurar fechas automáticamente si no vienen en el payload (refactoring-code-expert)
            current_time = datetime.now()
            created_at = landing.CreatedAt if landing.CreatedAt else current_time
            updated_at = landing.UpdatedAt if landing.UpdatedAt else current_time

            sql = """
                INSERT INTO Landings_Usuarios (
                    FK_ID_Dominios_Usuarios, Nombre, URL, Pixel, 
                    Cta_Link, FK_UserID, FK_ID_Bucket_Usuarios, 
                    Active, CreatedAt, UpdatedAt
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            # Prevención de SQL Injection: Uso estricto de consultas parametrizadas (security-audit)
            values = (
                landing.FK_ID_Dominios_Usuarios,
                landing.Nombre,
                landing.URL,
                landing.Pixel,
                landing.Cta_Link,
                landing.FK_UserID,
                landing.FK_ID_Bucket_Usuarios,
                landing.Active,
                created_at,
                updated_at
            )
            
            cursor.execute(sql, values)
            connection.commit()
            
            new_id: int = cursor.lastrowid
            
            # Retorno exacto solicitado en especificaciones, StatusCode 200 implícito en FastAPI
            return {
                "status": "success",
                "message": "Landing creada exitosamente",
                "data": {
                    "ID_Landing": new_id
                }
            }
    except pymysql.MySQLError as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al insertar el registro en Landings_Usuarios.",
                "details": str(e)
            }
        )
    finally:
        connection.close()

# -----------------------------------------------------------------------------
# Entry Point de Ejecución (senior-architect-engineering)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # En desarrollo local es buena práctica usar dotenv para inyectar credenciales.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass # En producción las env vars vienen del SO/Contenedor

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
