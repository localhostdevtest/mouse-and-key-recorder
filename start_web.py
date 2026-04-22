#!/usr/bin/env python3
"""
Grabador de Tareas - Interfaz Web
=================================

Aplicación web completa para grabar, gestionar y automatizar acciones de mouse y teclado
con sistema de prompts dinámicos integrado.

Características:
- Grabación y reproducción de acciones
- Gestión completa de tareas
- Teclado de prompts dinámicos
- Interfaz web moderna y responsive
- API REST integrada

Uso:
    python start_web.py

La aplicación estará disponible en: http://localhost:5000
"""

import os
import sys
import webbrowser
import threading
import time
from web_app import app, recorder

def check_dependencies():
    """Verifica que todas las dependencias estén instaladas"""
    try:
        import flask
        import pynput
        from PIL import Image
        print("[OK] Todas las dependencias están instaladas")
        return True
    except ImportError as e:
        print(f"[ERROR] Falta instalar dependencias: {e}")
        print("\n[INFO] Ejecuta: pip install -r requirements.txt")
        return False

def create_directories():
    """Crea los directorios necesarios"""
    directories = ['screenshots', 'templates', 'static/css', 'static/js']

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"[+] Creado directorio: {directory}")

def open_browser():
    """Abre el navegador después de un breve delay"""
    time.sleep(2)  # Esperar a que el servidor inicie
    try:
        webbrowser.open('http://localhost:5000')
        print("[INFO] Abriendo navegador...")
    except Exception as e:
        print(f"[WARNING] No se pudo abrir el navegador automáticamente: {e}")
        print("   Abre manualmente: http://localhost:5000")

def print_startup_info():
    """Muestra información de inicio"""
    print("\n" + "="*60)
    print("GRABADOR DE TAREAS - INTERFAZ WEB")
    print("="*60)
    print(f"URL: http://localhost:5000")
    print(f"Directorio: {os.getcwd()}")
    print(f"Tareas cargadas: {len(recorder.tasks)}")
    print("\nCARACTERISTICAS PRINCIPALES:")
    print("   - Grabación de acciones de mouse y teclado")
    print("   - Gestión completa de tareas")
    print("   - Teclado de prompts dinámicos")
    print("   - Interfaz web moderna y responsive")
    print("   - Compatible con dispositivos móviles")
    print("\nCOMO USAR:")
    print("   1. Haz clic en 'Iniciar Grabación'")
    print("   2. Realiza las acciones que quieres automatizar")
    print("   3. Detén la grabación y guarda como tarea")
    print("   4. Ve a 'Prompts' para crear plantillas dinámicas")
    print("   5. Genera prompts personalizados con contenido variable")
    print("\nIMPORTANTE:")
    print("   - Mantén esta ventana abierta mientras uses la aplicación")
    print("   - Para detener el servidor: Ctrl+C")
    print("="*60)

def main():
    """Función principal"""
    print("[INFO] Iniciando Grabador de Tareas...")

    # Verificar dependencias
    if not check_dependencies():
        sys.exit(1)

    # Crear directorios necesarios
    create_directories()

    # Mostrar información de inicio
    print_startup_info()

    # Abrir navegador en un hilo separado
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    try:
        print("\n[INFO] Iniciando servidor web...")
        print("   Presiona Ctrl+C para detener\n")

        # Iniciar aplicación Flask
        app.run(
            host='localhost',
            port=5000,
            debug=False,  # Desactivar debug para producción
            use_reloader=False  # Evitar reinicio automático
        )

    except KeyboardInterrupt:
        print("\n\n[INFO] Deteniendo servidor...")
        print("Gracias por usar el Grabador de Tareas!")

    except Exception as e:
        print(f"\n[ERROR] Error al iniciar el servidor: {e}")
        print("[INFO] Verifica que el puerto 5000 esté disponible")
        sys.exit(1)

if __name__ == "__main__":
    main()