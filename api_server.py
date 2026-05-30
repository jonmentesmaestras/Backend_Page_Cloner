import os
import uuid
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
    Token: str
    FK_ID_Bucket_Usuarios: int
    Active: int

class LandingUpdateURLs(BaseModel):
    uuid_landing: str
    URL_s3_final: str
    URL_cloudFront_final: str

# New model for deactivation
class LandingDeactivate(BaseModel):
    uuid_landing: str
# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.put("/api/v1/landings/deactivate")
def deactivate_landing(payload: LandingDeactivate) -> Dict[str, Any]:
    """
    Desactiva una landing (Active=0, UpdatedAt=now) usando uuid_landing.
    """
    # Validar formato UUID
    try:
        uuid.UUID(payload.uuid_landing)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "uuid_landing no tiene un formato UUID válido."
            }
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Actualizar Active y UpdatedAt
            sql = """
                UPDATE Landings_Usuarios
                SET Active = 0, UpdatedAt = %s
                WHERE uuid_landing = %s
            """
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(sql, (now, payload.uuid_landing))
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "Not Found",
                        "message": f"No se encontró ninguna landing con uuid_landing: {payload.uuid_landing}"
                    }
                )
            connection.commit()
            return {
                "success": True,
                "uuid_landing": payload.uuid_landing,
                "Active": 0,
                "UpdatedAt": now
            }
    except pymysql.MySQLError as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al desactivar la landing.",
                "details": str(e)
            }
        )
    finally:
        connection.close()

class BucketCreate(BaseModel):
    URL_Bucket: str
    Token: str
    FK_UserID: Optional[int] = None  # Deprecated, use Token instead
    URL_CloudFront: str
    Active: int
    CurrentSize: Optional[int] = 0
    CreatedAt: Optional[datetime] = None
    UpdatedAt: Optional[datetime] = None

class DomainCreate(BaseModel):
    Dominio: str
    Token: str
    NextDateRenew: datetime
    Active: int
    Price: float
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

def get_user_id_from_token(cursor: pymysql.cursors.DictCursor, token: str) -> int:
    """
    Resuelve el FK_UserID a partir de un token de acceso.
    Verifica que el token exista, esté activo y no haya expirado.
    """
    sql = """
        SELECT FK_UserID 
        FROM UserTokens 
        WHERE Token = %s 
          AND Active = 1 
          AND (Expires > NOW() OR Expires IS NULL)
        LIMIT 1
    """
    cursor.execute(sql, (token,))
    result = cursor.fetchone()
    
    if not result:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Unauthorized",
                "message": "Token inválido, inactivo o expirado."
            }
        )
    return result["FK_UserID"]

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
def get_landings_buckets(
    token: Optional[str] = None,
    id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Consulta todos los registros disponibles en la vista view_Landings_Buckets.
    Permite filtrar opcionalmente por usuario resolviendo el Token o por UUID de landing (id).
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if id is not None:
                # Validar formato UUID y buscar por uuid_landing
                try:
                    uuid.UUID(id)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "Bad Request",
                            "message": "id no tiene un formato UUID válido."
                        }
                    )
                sql = "SELECT * FROM view_Landings_Buckets WHERE uuid_landing = %s;"
                cursor.execute(sql, (id,))
            elif token is not None:
                # Resolver UserID a partir del Token
                user_id = get_user_id_from_token(cursor, token)
                # Consulta filtrada con parámetro estricto para evitar SQLi (security-audit)
                sql = "SELECT * FROM view_Landings_Buckets WHERE UserID = %s;"
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
            # Validar token y obtener UserID
            user_id = get_user_id_from_token(cursor, landing.Token)
            landing_uuid = str(uuid.uuid4())

            # Generar fechas con formato YYYY-MM-DD HH:mm:ss
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sql = """
                INSERT INTO Landings_Usuarios (
                    uuid_landing,
                    FK_ID_Dominios_Usuarios, Nombre, URL, 
                    FK_UserID, FK_ID_Bucket_Usuarios, 
                    Active, CreatedAt, UpdatedAt
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            # Prevención de SQL Injection: Uso estricto de consultas parametrizadas (security-audit)
            values = (
                landing_uuid,
                landing.FK_ID_Dominios_Usuarios,
                landing.Nombre,
                landing.URL,
                user_id,
                landing.FK_ID_Bucket_Usuarios,
                landing.Active,
                current_time,
                current_time
            )
            
            cursor.execute(sql, values)
            connection.commit()
            
            new_id: int = cursor.lastrowid
            
            # Retorno exacto solicitado en especificaciones, StatusCode 200 implícito en FastAPI
            return {
                "status": "success",
                "message": "Landing creada exitosamente",
                "data": {
                    "ID_Landing": new_id,
                    "uuid_landing":landing_uuid
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

@app.put("/api/v1/landings/url-s3")
def update_landing_url_s3(payload: LandingUpdateURLs) -> Dict[str, Any]:
    """
    Actualiza los campos URL_s3_final y URL_cloudFront_final en la tabla Landings_Usuarios usando el uuid_landing.
    """
    # Validar formato UUID
    try:
        uuid.UUID(payload.uuid_landing)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "uuid_landing no tiene un formato UUID válido."
            }
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 2. Ejecutar la actualización de ambos campos
            sql = """
                UPDATE Landings_Usuarios 
                SET URL_s3_final = %s, URL_cloudFront_final = %s 
                WHERE uuid_landing = %s
            """
            cursor.execute(sql, (payload.URL_s3_final, payload.URL_cloudFront_final, payload.uuid_landing))
            
            # Verificar si se actualizó alguna fila
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "Not Found",
                        "message": f"No se encontró ninguna landing con uuid_landing: {payload.uuid_landing}"
                    }
                )

            connection.commit()
            
            # 3. Respuesta solicitada
            return {
                "success": True,
                "URL_s3_final": payload.URL_s3_final,
                "URL_cloudFront_final": payload.URL_cloudFront_final
            }
    except pymysql.MySQLError as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al actualizar URL_s3_final y URL_cloudFront_final.",
                "details": str(e)
            }
        )
    finally:
        connection.close()

@app.post("/api/v1/buckets")
def create_bucket(bucket: BucketCreate) -> Dict[str, Any]:
    """
    Inserta una nueva fila en la tabla AWSBucket_Usuarios.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Validar token y obtener UserID
            user_id = get_user_id_from_token(cursor, bucket.Token)

            # Configurar fechas automáticamente
            current_time = datetime.now()
            created_at = bucket.CreatedAt if bucket.CreatedAt else current_time
            updated_at = bucket.UpdatedAt if bucket.UpdatedAt else current_time

            sql = """
                INSERT INTO AWSBucket_Usuarios (
                    URL_Bucket, FK_UserID, URL_CloudFront, 
                    Active, CurrentSize, CreatedAt, UpdatedAt
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                bucket.URL_Bucket,
                user_id,
                bucket.URL_CloudFront,
                bucket.Active,
                bucket.CurrentSize,
                created_at,
                updated_at
            )
            
            cursor.execute(sql, values)
            connection.commit()
            
            new_id: int = cursor.lastrowid
            
            return {
                "status": "success",
                "message": "Bucket creado exitosamente",
                "data": {
                    "ID_Bucket_Usuarios": new_id
                }
            }
    except pymysql.MySQLError as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al insertar el registro en AWSBucket_Usuarios.",
                "details": str(e)
            }
        )
    finally:
        connection.close()

@app.post("/api/v1/domains")
def create_domain(domain: DomainCreate) -> Dict[str, Any]:
    """
    Inserta una nueva fila en la tabla Dominios_Usuarios.
    """
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Validar token y obtener UserID
            user_id = get_user_id_from_token(cursor, domain.Token)

            # Configurar fechas automáticamente
            current_time = datetime.now()
            created_at = domain.CreatedAt if domain.CreatedAt else current_time
            updated_at = domain.UpdatedAt if domain.UpdatedAt else current_time

            sql = """
                INSERT INTO Dominios_Usuarios (
                    FK_UserID, Dominio, NextDateRenew, 
                    Active, Price, CreatedAt, UpdatedAt
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                user_id,
                domain.Dominio,
                domain.NextDateRenew,
                domain.Active,
                domain.Price,
                created_at,
                updated_at
            )
            
            cursor.execute(sql, values)
            connection.commit()
            
            new_id: int = cursor.lastrowid
            
            return {
                "status": "success",
                "message": "Dominio creado exitosamente",
                "data": {
                    "ID_Dominios_Usuarios": new_id
                }
            }
    except pymysql.MySQLError as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Error al insertar el registro en Dominios_Usuarios.",
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
