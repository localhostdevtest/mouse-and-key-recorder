# Grabador de Mouse y Teclado con Sistema de Tareas y API HTTP

Una aplicación completa en Python para grabar, gestionar y automatizar acciones de mouse y teclado, con servidor HTTP integrado para ejecución remota.

## 🚀 Características Principales

### 🔴 **Grabación y Reproducción**
- Captura todos los movimientos del mouse, clics y teclas presionadas
- Reproduce exactamente las acciones grabadas con tiempos precisos
- Interfaz gráfica intuitiva con controles fáciles de usar

### 📋 **Sistema de Gestión de Tareas**
- Guarda grabaciones como tareas reutilizables con nombres y descripciones
- Organiza y gestiona bibliotecas completas de tareas automatizadas
- Edita, duplica y elimina tareas según necesites
- Ejecuta tareas individuales o en secuencias complejas

### 🌐 **Servidor HTTP API**
- Servidor HTTP local integrado para ejecución remota
- Ejecuta tareas desde otros programas, scripts o aplicaciones
- API REST completa con endpoints para todas las funcionalidades
- Documentación interactiva incluida en la aplicación

### 📸 **Captura de Pantalla**
- Selección interactiva de área específica para capturar
- Guardado automático con timestamps
- Integración completa con el sistema de tareas

## 📦 Instalación

1. Clona o descarga este repositorio
2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## 🎯 Uso Básico

### Ejecutar la Aplicación
```bash
python recorder.py
```

### 1. **Crear Tareas** (Pestaña "🔴 Grabación")
1. Haz clic en "🔴 Grabar"
2. Realiza las acciones que quieres automatizar
3. Haz clic en "⏹️ Parar"
4. Ingresa un nombre para la tarea (ej: "Abrir Excel")
5. Opcionalmente agrega una descripción
6. Haz clic en "💾 Guardar como Tarea"

### 2. **Gestionar Tareas** (Pestaña "📋 Tareas")
- **Ver tareas**: Lista completa en el panel izquierdo
- **Editar**: Selecciona una tarea y haz clic en "✏️ Editar"
- **Duplicar**: Crea copias de tareas existentes
- **Eliminar**: Borra tareas que ya no necesites

### 3. **Ejecutar Tareas**

#### **Opción A - Tarea Individual:**
1. Selecciona una tarea de la lista
2. Haz clic en "▶️ Ejecutar Seleccionada"

#### **Opción B - Cola de Tareas:**
1. Selecciona las tareas que quieres ejecutar
2. Haz clic en "➕ Agregar a Cola"
3. Configura la pausa entre tareas
4. Opcionalmente activa "Repetir cola continuamente"
5. Haz clic en "▶️ Ejecutar Cola"

### 4. **Servidor HTTP API** (Pestaña "🌐 API Server")
1. Haz clic en "🚀 Iniciar Servidor"
2. El servidor se ejecutará en `http://localhost:PUERTO`
3. Usa la API desde otros programas o scripts

## 🌐 API HTTP - Endpoints

### **Base URL:** `http://localhost:PUERTO`

#### **GET /api/status**
Obtiene el estado del servidor
```bash
curl http://localhost:8080/api/status
```

#### **GET /api/tasks**
Lista todas las tareas disponibles
```bash
curl http://localhost:8080/api/tasks
```

#### **POST /api/execute/task**
Ejecuta una tarea específica
```bash
curl -X POST http://localhost:8080/api/execute/task \
     -H "Content-Type: application/json" \
     -d '{"task_name": "mi_tarea"}'
```

#### **POST /api/execute/queue**
Ejecuta una cola de tareas
```bash
curl -X POST http://localhost:8080/api/execute/queue \
     -H "Content-Type: application/json" \
     -d '{"tasks": ["tarea1", "tarea2"], "pause_time": 1.5, "repeat": false}'
```

#### **POST /api/execute/custom-queue**
Ejecuta una cola personalizada con configuración avanzada
```bash
curl -X POST http://localhost:8080/api/execute/custom-queue \
     -H "Content-Type: application/json" \
     -d '{
       "queue": {
         "tasks": [
           "tarea_simple",
           {
             "name": "tarea_con_config",
             "pause_after": 3.0,
             "repeat_task": 2
           }
         ],
         "global_pause_time": 1.0,
         "repeat": true,
         "repeat_count": 5
       }
     }'
```

## 🐍 Ejemplos en Python

### Ejecutar una tarea
```python
import requests

response = requests.post('http://localhost:8080/api/execute/task',
                        json={'task_name': 'mi_tarea'})
print(response.json())
```

### Ejecutar cola de tareas
```python
import requests

response = requests.post('http://localhost:8080/api/execute/queue',
                        json={
                            'tasks': ['tarea1', 'tarea2', 'tarea3'],
                            'pause_time': 2.0,
                            'repeat': False
                        })
print(response.json())
```

### Script de prueba completo
```bash
python test_api.py
```

## 🎛️ Características Avanzadas

### **Configuración de Ejecución**
- **Pausa entre tareas**: Tiempo de espera configurable
- **Modo repetición**: Ejecuta colas continuamente
- **Repetición de tareas individuales**: Repite tareas específicas múltiples veces
- **Estado en tiempo real**: Monitoreo del progreso de ejecución

### **Gestión de Archivos**
- **Persistencia automática**: Todas las tareas se guardan en `tasks.json`
- **Carga automática**: Restaura tareas al iniciar la aplicación
- **Exportar/Importar**: Guarda grabaciones individuales en archivos JSON
- **Screenshots organizados**: Carpeta `screenshots/` con timestamps

### **Servidor HTTP**
- **Puerto automático**: Encuentra puertos disponibles automáticamente
- **Ejecución asíncrona**: Las tareas no bloquean el servidor
- **Manejo de errores**: Respuestas HTTP apropiadas (400, 404, 500)
- **Documentación integrada**: Guía completa en la aplicación

## 📁 Estructura de Archivos

```
📁 Proyecto/
├── 📄 recorder.py          # Aplicación principal
├── 📄 test_api.py          # Script de prueba de la API
├── 📄 requirements.txt     # Dependencias
├── 📄 tasks.json          # Tareas guardadas (se crea automáticamente)
├── 📁 screenshots/        # Screenshots capturados
└── 📄 README.md           # Esta documentación
```

## 🎯 Casos de Uso Prácticos

### **Automatización de Oficina**
```python
# Rutina matutina automatizada
tasks = ["abrir_aplicaciones", "revisar_emails", "actualizar_reportes"]
requests.post('http://localhost:8080/api/execute/queue',
              json={'tasks': tasks, 'pause_time': 3.0})
```

### **Testing Automatizado**
```python
# Pruebas repetitivas
queue_config = {
    "tasks": [
        {"name": "llenar_formulario", "repeat_task": 10},
        "enviar_datos",
        "verificar_resultado"
    ],
    "repeat": True,
    "repeat_count": 100
}
requests.post('http://localhost:8080/api/execute/custom-queue',
              json={'queue': queue_config})
```

### **Procesamiento de Datos**
```python
# Procesamiento por lotes
tasks = ["abrir_archivo", "procesar_datos", "guardar_resultado"]
requests.post('http://localhost:8080/api/execute/queue',
              json={'tasks': tasks, 'pause_time': 5.0, 'repeat': True})
```

## 🔧 Dependencias

- `pynput`: Captura y simulación de eventos de mouse y teclado
- `Pillow`: Procesamiento de imágenes para screenshots
- `Flask`: Servidor HTTP para la API
- `tkinter`: Interfaz gráfica (incluido con Python)

## 🖥️ Compatibilidad

- ✅ **Windows** (Probado)
- ✅ **macOS** (Compatible)
- ✅ **Linux** (Compatible)

## ⚠️ Notas Importantes

### **Permisos**
- En algunos sistemas puede requerir permisos de administrador
- **macOS**: Agregar Python a Preferencias > Seguridad > Privacidad > Accesibilidad
- **Linux**: Puede requerir permisos adicionales según la distribución

### **Seguridad**
- El servidor HTTP se ejecuta solo en `localhost` por seguridad
- Las tareas se ejecutan con los mismos permisos que la aplicación
- **Cuidado**: La reproducción ejecuta exactamente las mismas acciones grabadas

### **Rendimiento**
- Las tareas se ejecutan de forma asíncrona para no bloquear la interfaz
- El servidor puede manejar múltiples peticiones simultáneas
- Los tiempos de reproducción son precisos al milisegundo

## 🆘 Solución de Problemas

### **Error de permisos**
```bash
# Windows: Ejecutar como administrador
# macOS: Agregar permisos de accesibilidad
# Linux: Verificar permisos de X11
```

### **Puerto ocupado**
- La aplicación encuentra automáticamente un puerto disponible
- Verifica que no haya otras instancias ejecutándose

### **API no responde**
```bash
# Probar conexión
python test_api.py

# Verificar estado del servidor en la pestaña "API Server"
```

### **Tareas no se ejecutan**
- Verifica que las tareas existan en la lista
- Comprueba los nombres de tareas (case-sensitive)
- Revisa los logs en la consola de la aplicación

## 🤝 Contribuciones

Este proyecto es de código abierto. Las contribuciones son bienvenidas:

1. Fork del repositorio
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto. Úsalo libremente para tus necesidades.

---

## 🎉 ¡Disfruta automatizando tus tareas!

Con esta aplicación puedes crear bibliotecas completas de automatizaciones y ejecutarlas desde cualquier programa o script. ¡Las posibilidades son infinitas!