# 🚀 DOCUMENTACIÓN COMPLETA DE API PARA POSTMAN

## 🌐 BASE URL
```
http://localhost:5000
```

---

## 📋 **1. LISTAR TODO (Automatizaciones y Secuencias)**

### GET `/api/list-all`
**Descripción:** Lista todas las automatizaciones y secuencias disponibles

**URL Completa:** `http://localhost:5000/api/list-all`

**Método:** GET

**Headers:** Ninguno requerido

**Body:** Ninguno

**Respuesta de ejemplo:**
```json
{
  "automation_count": 3,
  "automations": {
    "automatizacion_1": {
      "name": "automatizacion_1",
      "description": "Primera automatización",
      "event_count": 3,
      "created_at": "2026-04-22T13:15:00"
    }
  },
  "sequence_count": 1,
  "sequences": {
    "mi_secuencia": {
      "name": "mi_secuencia",
      "tasks": ["automatizacion_1", "automatizacion_2"],
      "pause_between": 1.0
    }
  }
}
```

---

## 🎯 **2. EJECUTAR UNA AUTOMATIZACIÓN ESPECÍFICA**

### POST `/api/run/{nombre_automatizacion}`
**Descripción:** Ejecuta una automatización específica al instante

**URL Completa:** `http://localhost:5000/api/run/automatizacion_1`

**Método:** POST

**Headers:** 
```
Content-Type: application/json
```

**Body:** Ninguno

**Ejemplo en Postman:**
- URL: `http://localhost:5000/api/run/automatizacion_1`
- Método: POST
- Body: (vacío)

**Respuesta:**
```json
{
  "success": true,
  "message": "Tarea 'automatizacion_1' iniciada"
}
```

---

## ⚡ **3. EJECUTAR MÚLTIPLES AUTOMATIZACIONES AL INSTANTE**

### POST `/api/quick-sequence`
**Descripción:** Ejecuta varias automatizaciones en secuencia sin guardar la secuencia

**URL Completa:** `http://localhost:5000/api/quick-sequence`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "tasks": ["automatizacion_1", "automatizacion_2", "automatizacion_3"],
  "pause_between": 2.0
}
```

**Parámetros del Body:**
- `tasks` (array): Lista de nombres de automatizaciones a ejecutar
- `pause_between` (number): Segundos de pausa entre cada automatización

**Respuesta:**
```json
{
  "success": true,
  "message": "Ejecutando 3 automatizaciones en secuencia"
}
```

---

## 📝 **4. CREAR SECUENCIA PERMANENTE**

### POST `/api/sequences/create`
**Descripción:** Crea una secuencia que se guarda permanentemente

**URL Completa:** `http://localhost:5000/api/sequences/create`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "name": "Mi_Secuencia_Completa",
  "tasks": ["automatizacion_1", "automatizacion_2", "automatizacion_3"],
  "description": "Secuencia que ejecuta las 3 automatizaciones",
  "pause_between": 1.5
}
```

**Parámetros del Body:**
- `name` (string, requerido): Nombre único de la secuencia
- `tasks` (array, requerido): Lista de automatizaciones a incluir
- `description` (string, opcional): Descripción de la secuencia
- `pause_between` (number, opcional): Pausa entre automatizaciones (default: 1.0)

**Respuesta:**
```json
{
  "success": true,
  "message": "Secuencia 'Mi_Secuencia_Completa' creada correctamente"
}
```

---

## 🎯 **5. EJECUTAR SECUENCIA GUARDADA**

### POST `/api/run-sequence/{nombre_secuencia}`
**Descripción:** Ejecuta una secuencia previamente guardada

**URL Completa:** `http://localhost:5000/api/run-sequence/Mi_Secuencia_Completa`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body:** Ninguno

**Respuesta:**
```json
{
  "success": true,
  "message": "Secuencia 'Mi_Secuencia_Completa' iniciada"
}
```

---

## 📋 **6. LISTAR SOLO AUTOMATIZACIONES**

### GET `/api/tasks/list`
**Descripción:** Lista solo las automatizaciones (sin secuencias)

**URL Completa:** `http://localhost:5000/api/tasks/list`

**Método:** GET

**Headers:** Ninguno

**Body:** Ninguno

**Respuesta:**
```json
{
  "tasks": {
    "automatizacion_1": {
      "name": "automatizacion_1",
      "description": "Primera automatización",
      "event_count": 3,
      "created_at": "2026-04-22T13:15:00"
    }
  }
}
```

---

## 📋 **7. LISTAR SOLO SECUENCIAS**

### GET `/api/sequences/list`
**Descripción:** Lista solo las secuencias (sin automatizaciones)

**URL Completa:** `http://localhost:5000/api/sequences/list`

**Método:** GET

**Headers:** Ninguno

**Body:** Ninguno

**Respuesta:**
```json
{
  "sequences": {
    "Mi_Secuencia_Completa": {
      "name": "Mi_Secuencia_Completa",
      "tasks": ["automatizacion_1", "automatizacion_2"],
      "description": "Mi secuencia de prueba",
      "pause_between": 1.5,
      "task_count": 2,
      "created_at": "2026-04-22T13:20:00"
    }
  }
}
```

---

## 🗑️ **8. ELIMINAR AUTOMATIZACIÓN**

### DELETE `/api/tasks/delete/{nombre_automatizacion}`
**Descripción:** Elimina una automatización permanentemente

**URL Completa:** `http://localhost:5000/api/tasks/delete/automatizacion_1`

**Método:** DELETE

**Headers:**
```
Content-Type: application/json
```

**Body:** Ninguno

**Respuesta:**
```json
{
  "success": true,
  "message": "Tarea \"automatizacion_1\" eliminada"
}
```

---

## 🗑️ **9. ELIMINAR SECUENCIA**

### DELETE `/api/sequences/delete/{nombre_secuencia}`
**Descripción:** Elimina una secuencia permanentemente

**URL Completa:** `http://localhost:5000/api/sequences/delete/Mi_Secuencia_Completa`

**Método:** DELETE

**Headers:**
```
Content-Type: application/json
```

**Body:** Ninguno

**Respuesta:**
```json
{
  "success": true,
  "message": "Secuencia \"Mi_Secuencia_Completa\" eliminada"
}
```

---

## 🔄 **10. CONTROL DE GRABACIÓN**

### POST `/api/recording/start`
**Descripción:** Inicia la grabación de una nueva automatización

**URL Completa:** `http://localhost:5000/api/recording/start`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body:** Ninguno

**Respuesta:**
```json
{
  "success": true,
  "message": "Grabación iniciada"
}
```

### POST `/api/recording/stop`
**Descripción:** Detiene la grabación actual

**URL Completa:** `http://localhost:5000/api/recording/stop`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body:** Ninguno

**Respuesta:**
```json
{
  "success": true,
  "message": "Grabación detenida. 15 eventos capturados",
  "event_count": 15
}
```

### GET `/api/recording/status`
**Descripción:** Obtiene el estado actual de la grabación

**URL Completa:** `http://localhost:5000/api/recording/status`

**Método:** GET

**Headers:** Ninguno

**Body:** Ninguno

**Respuesta:**
```json
{
  "is_recording": false,
  "event_count": 0
}
```

---

## 💾 **11. GUARDAR AUTOMATIZACIÓN DESPUÉS DE GRABAR**

### POST `/api/tasks/save`
**Descripción:** Guarda la grabación actual como una automatización

**URL Completa:** `http://localhost:5000/api/tasks/save`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "name": "Mi_Nueva_Automatizacion",
  "description": "Descripción opcional",
  "prompt_template": "Plantilla de prompt opcional"
}
```

**Parámetros del Body:**
- `name` (string, requerido): Nombre de la automatización
- `description` (string, opcional): Descripción
- `prompt_template` (string, opcional): Plantilla de prompt para IA

**Respuesta:**
```json
{
  "success": true,
  "message": "Tarea 'Mi_Nueva_Automatizacion' guardada correctamente"
}
```

---

## 🚀 **EJEMPLOS PRÁCTICOS PARA POSTMAN**

### **Ejemplo 1: Ejecutar una automatización**
```bash
curl -X POST http://localhost:5000/api/run/automatizacion_1
```

### **Ejemplo 2: Ejecutar 3 automatizaciones en secuencia**
```bash
curl -X POST http://localhost:5000/api/quick-sequence \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": ["automatizacion_1", "automatizacion_2", "automatizacion_3"],
    "pause_between": 2.0
  }'
```

### **Ejemplo 3: Crear una secuencia permanente**
```bash
curl -X POST http://localhost:5000/api/sequences/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Secuencia_Completa",
    "tasks": ["automatizacion_1", "automatizacion_2"],
    "description": "Mi secuencia de prueba",
    "pause_between": 1.5
  }'
```

### **Ejemplo 4: Ver todo lo disponible**
```bash
curl http://localhost:5000/api/list-all
```

---

## ⚠️ **NOTAS IMPORTANTES**

1. **Persistencia:** Todo se guarda automáticamente en archivos locales
2. **Puerto:** El servidor corre en puerto 5000 por defecto
3. **Formato:** Todas las respuestas son en formato JSON
4. **Errores:** Los errores devuelven `{"success": false, "message": "descripción del error"}`
5. **Ejecución:** Las automatizaciones se ejecutan de forma asíncrona
6. **Nombres:** Los nombres de automatizaciones y secuencias son case-sensitive

---

## 🔧 **CÓDIGOS DE RESPUESTA HTTP**

- **200:** Operación exitosa
- **400:** Error en los parámetros enviados
- **404:** Automatización o secuencia no encontrada
- **500:** Error interno del servidor