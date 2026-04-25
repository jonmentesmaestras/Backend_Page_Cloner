Especificaciones Técnicas para Agente Antigravity: API REST en Python

Objetivo del Agente: Construir una API REST en Python (preferiblemente usando FastAPI o Flask) para interactuar con una base de datos MariaDB. La API debe habilitar operaciones CRUD (Create, Read) específicas para las tablas y vistas del sistema de Landings.

Requisitos Generales:

Lenguaje: Python 3.9+

Respuestas: Todas las respuestas deben ser devueltas en formato JSON.

Manejo de Errores: Implementar bloques try-except para capturar excepciones de base de datos y retornar los códigos de estado HTTP apropiados.

Endpoint 1: Consultar Vista de Landings y Buckets (READ)

Ruta sugerida: GET /api/v1/landings-buckets

Descripción:
Consulta todos los registros disponibles en la vista Vista_Landings_Buckets y retorna la información consolidada.

Comportamiento Esperado:

Conectar a la base de datos MariaDB.

Ejecutar el query: SELECT * FROM Vista_Landings_Buckets;

Formatear los resultados en una lista de diccionarios (JSON).

Respuestas:

Status 200 (Success):
Retorna un JSON con el array de resultados.

[
  {
    "URL_Bucket": "s3-bucket-url",
    "URL_CloudFront": "cloudfront-url",
    "Bucket_Active": 1,
    "Nombre": "Mi Landing Page",
    "Landing_URL": "[https://midominio.com](https://midominio.com)",
    "FK_UserID": 105,
    "Landing_Active": 1,
    "CreatedAt": "2023-10-25T10:00:00",
    "UpdatedAt": "2023-10-25T10:00:00"
  }
]


Status 500 (Internal Server Error):
Si hay un error en la conexión, un error de sintaxis en el SQL, o una excepción inesperada.

{
  "error": "Internal Server Error",
  "message": "Error al consultar la vista de landings y buckets.",
  "details": "<Excepción de Python o error del driver SQL>"
}


Endpoint 2: Insertar nueva Landing (CREATE)

Ruta sugerida: POST /api/v1/landings

Descripción:
Recibe un payload JSON e inserta una nueva fila en la tabla Landings_Usuarios.

Comportamiento Esperado:

Recibir y validar el JSON entrante.

Conectar a la base de datos MariaDB.

Configurar dinámicamente el CreatedAt y UpdatedAt con la fecha y hora actual del servidor, a menos que vengan en el payload.

Ejecutar el query de inserción en Landings_Usuarios.

Estructura del Payload Esperado (Input):

{
  "FK_ID_Dominios_Usuarios": 12,
  "Nombre": "Campaña Black Friday",
  "URL": "[https://midominio.com/black-friday](https://midominio.com/black-friday)",
  "Pixel": "1234567890",
  "Cta_Link": "[https://checkout.com/buy](https://checkout.com/buy)",
  "FK_UserID": 105,
  "FK_ID_Bucket_Usuarios": 3,
  "Active": 1
}


Respuestas:

Status 200 (Success):
Confirma la inserción exitosa y, de ser posible, retorna el ID generado (Auto_increment). (Nota para el agente: aunque el estándar REST a veces sugiere 201 Created, por requerimientos específicos se debe retornar 200).

{
  "status": "success",
  "message": "Landing creada exitosamente",
  "data": {
    "ID_Landing": 42
  }
}


Status 500 (Internal Server Error):
Si falla la inserción por problemas de integridad referencial (FKs no válidas), valores nulos no permitidos, o caída de DB.

{
  "error": "Internal Server Error",
  "message": "Error al insertar el registro en Landings_Usuarios.",
  "details": "<Mensaje del driver, e.g., Foreign Key constraint failed>"
}
