# Grabador de Mouse y Teclado

Una aplicación simple en Python para grabar y reproducir acciones de mouse y teclado.

## Características

- 🔴 **Grabar**: Captura todos los movimientos del mouse, clics y teclas presionadas
- ▶️ **Reproducir**: Reproduce exactamente las acciones grabadas con los tiempos correctos
- 💾 **Guardar/Cargar**: Guarda las grabaciones en archivos JSON para uso posterior
- 🎯 **Interfaz simple**: Interfaz gráfica fácil de usar con botones intuitivos

## Instalación

1. Clona o descarga este repositorio
2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Uso

1. Ejecuta la aplicación:

```bash
python recorder.py
```

2. **Para grabar**:
   - Haz clic en "🔴 Grabar"
   - Realiza las acciones que quieres grabar (movimientos de mouse, clics, teclas)
   - Haz clic en "⏹️ Parar" cuando termines

3. **Para reproducir**:
   - Haz clic en "▶️ Reproducir"
   - La aplicación repetirá exactamente lo que grabaste

4. **Guardar/Cargar grabaciones**:
   - Usa "💾 Guardar Grabación" para guardar en un archivo
   - Usa "📁 Cargar Grabación" para cargar una grabación anterior

## Controles

- **🔴 Grabar**: Inicia la grabación de eventos
- **⏹️ Parar**: Detiene la grabación actual
- **▶️ Reproducir**: Reproduce la grabación
- **🗑️ Limpiar**: Borra la grabación actual
- **💾 Guardar**: Guarda la grabación en archivo JSON
- **📁 Cargar**: Carga una grabación desde archivo

## Notas Importantes

- ⚠️ **Permisos**: En algunos sistemas puede requerir permisos de administrador
- ⚠️ **Cuidado**: La reproducción ejecutará exactamente las mismas acciones, incluyendo clics en botones
- 💡 **Tip**: Prueba primero con acciones simples antes de grabar secuencias complejas

## Dependencias

- `pynput`: Para capturar y simular eventos de mouse y teclado
- `tkinter`: Para la interfaz gráfica (incluido con Python)

## Compatibilidad

- ✅ Windows
- ✅ macOS  
- ✅ Linux

## Solución de Problemas

### Error de permisos
Si obtienes errores de permisos:
- **Windows**: Ejecuta como administrador
- **macOS**: Ve a Preferencias del Sistema > Seguridad y Privacidad > Privacidad > Accesibilidad y agrega Python/Terminal
- **Linux**: Puede requerir permisos adicionales dependiendo de la distribución

### La aplicación no responde
- Asegúrate de hacer clic en "Parar" para terminar la grabación
- Si se congela, cierra y vuelve a abrir la aplicación

## Formato de Archivo

Las grabaciones se guardan en formato JSON con la siguiente estructura:

```json
[
  {
    "type": "mouse_move",
    "x": 100,
    "y": 200,
    "time": 0.5
  },
  {
    "type": "mouse_click", 
    "x": 100,
    "y": 200,
    "button": "left",
    "pressed": true,
    "time": 1.0
  }
]
```

## Licencia

Este proyecto es de código abierto. Úsalo libremente para tus necesidades.