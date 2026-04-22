# 🚀 API ULTRA SIMPLE PARA POSTMAN

## BASE URL: http://localhost:5000

## 📋 LISTAR TODO
GET /api/list-all
- Lista todas las automatizaciones y secuencias

## 🎯 EJECUTAR UNA AUTOMATIZACIÓN
POST /api/run/NOMBRE_AUTOMATIZACION
- Ejemplo: POST /api/run/mi_automatizacion

## 🎯 EJECUTAR UNA SECUENCIA
POST /api/run-sequence/NOMBRE_SECUENCIA
- Ejemplo: POST /api/run-sequence/mi_secuencia

## ⚡ EJECUTAR VARIAS AUTOMATIZACIONES AL INSTANTE
POST /api/quick-sequence
Body (JSON):
{
  "tasks": ["automatizacion1", "automatizacion2", "automatizacion3"],
  "pause_between": 2.0
}

## 📝 CREAR SECUENCIA PERMANENTE
POST /api/sequences/create
Body (JSON):
{
  "name": "Mi Secuencia",
  "tasks": ["automatizacion1", "automatizacion2"],
  "description": "Descripción opcional",
  "pause_between": 1.5
}

## 📋 LISTAR SECUENCIAS
GET /api/sequences/list

## 🗑️ ELIMINAR SECUENCIA
DELETE /api/sequences/delete/NOMBRE_SECUENCIA

## 📋 LISTAR AUTOMATIZACIONES
GET /api/tasks/list

## 🗑️ ELIMINAR AUTOMATIZACIÓN
DELETE /api/tasks/delete/NOMBRE_AUTOMATIZACION

## EJEMPLOS PRÁCTICOS:

### Ejecutar una automatización:
curl -X POST http://localhost:5000/api/run/mi_automatizacion

### Ejecutar 3 automatizaciones en secuencia:
curl -X POST http://localhost:5000/api/quick-sequence \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["auto1", "auto2", "auto3"], "pause_between": 1.0}'

### Ver todo lo que tienes:
curl http://localhost:5000/api/list-all