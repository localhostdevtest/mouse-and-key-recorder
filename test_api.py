#!/usr/bin/env python3
"""
Script de prueba para la API HTTP del Grabador de Mouse y Teclado

Este script demuestra cómo usar la API HTTP para ejecutar tareas
desde otros programas o scripts.
"""

import requests
import json
import time
import sys

class TaskRecorderAPI:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url

    def get_status(self):
        """Obtiene el estado del servidor"""
        try:
            response = requests.get(f"{self.base_url}/api/status")
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            print(f"Error conectando al servidor: {e}")
            return None

    def get_tasks(self):
        """Obtiene la lista de tareas disponibles"""
        try:
            response = requests.get(f"{self.base_url}/api/tasks")
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo tareas: {e}")
            return None

    def execute_task(self, task_name):
        """Ejecuta una tarea específica"""
        try:
            data = {"task_name": task_name}
            response = requests.post(f"{self.base_url}/api/execute/task", json=data)
            return response.json(), response.status_code
        except requests.exceptions.RequestException as e:
            print(f"Error ejecutando tarea: {e}")
            return None, 500

    def execute_queue(self, tasks, pause_time=1.0, repeat=False):
        """Ejecuta una cola de tareas"""
        try:
            data = {
                "tasks": tasks,
                "pause_time": pause_time,
                "repeat": repeat
            }
            response = requests.post(f"{self.base_url}/api/execute/queue", json=data)
            return response.json(), response.status_code
        except requests.exceptions.RequestException as e:
            print(f"Error ejecutando cola: {e}")
            return None, 500

    def execute_custom_queue(self, queue_config):
        """Ejecuta una cola personalizada"""
        try:
            data = {"queue": queue_config}
            response = requests.post(f"{self.base_url}/api/execute/custom-queue", json=data)
            return response.json(), response.status_code
        except requests.exceptions.RequestException as e:
            print(f"Error ejecutando cola personalizada: {e}")
            return None, 500

def main():
    print("🧪 Script de Prueba - API del Grabador de Tareas")
    print("=" * 50)

    # Crear instancia de la API
    api = TaskRecorderAPI()

    # Probar conexión
    print("1. Probando conexión al servidor...")
    status = api.get_status()
    if not status:
        print("❌ No se pudo conectar al servidor.")
        print("   Asegúrate de que la aplicación esté ejecutándose y el servidor HTTP esté iniciado.")
        return

    print(f"✅ Servidor conectado en puerto {status['server_port']}")
    print(f"   Tareas disponibles: {status['tasks_count']}")

    # Obtener lista de tareas
    print("\n2. Obteniendo lista de tareas...")
    tasks_data = api.get_tasks()
    if not tasks_data or tasks_data['count'] == 0:
        print("⚠️  No hay tareas disponibles.")
        print("   Crea algunas tareas en la aplicación primero.")
        return

    print(f"✅ Encontradas {tasks_data['count']} tareas:")
    task_names = []
    for name, task in tasks_data['tasks'].items():
        print(f"   • {name} - {task['event_count']} eventos")
        if task['description']:
            print(f"     Descripción: {task['description']}")
        task_names.append(name)

    # Ejemplos de ejecución
    print("\n3. Ejemplos de ejecución:")

    if len(task_names) >= 1:
        print(f"\n   Ejemplo 1: Ejecutar tarea individual '{task_names[0]}'")
        choice = input("   ¿Ejecutar? (y/n): ").lower().strip()
        if choice == 'y':
            result, status_code = api.execute_task(task_names[0])
            if status_code == 200:
                print(f"   ✅ {result['message']}")
            else:
                print(f"   ❌ Error: {result.get('error', 'Error desconocido')}")

    if len(task_names) >= 2:
        print(f"\n   Ejemplo 2: Ejecutar cola de tareas")
        selected_tasks = task_names[:2]  # Primeras 2 tareas
        print(f"   Tareas: {selected_tasks}")
        choice = input("   ¿Ejecutar cola? (y/n): ").lower().strip()
        if choice == 'y':
            result, status_code = api.execute_queue(selected_tasks, pause_time=2.0)
            if status_code == 200:
                print(f"   ✅ {result['message']}")
            else:
                print(f"   ❌ Error: {result.get('error', 'Error desconocido')}")

    if len(task_names) >= 1:
        print(f"\n   Ejemplo 3: Cola personalizada con repetición")
        custom_config = {
            "tasks": [
                task_names[0],  # Tarea simple
                {
                    "name": task_names[0],
                    "pause_after": 3.0,
                    "repeat_task": 2
                }
            ],
            "global_pause_time": 1.0,
            "repeat": False,
            "repeat_count": 1
        }
        print(f"   Configuración: {json.dumps(custom_config, indent=2)}")
        choice = input("   ¿Ejecutar cola personalizada? (y/n): ").lower().strip()
        if choice == 'y':
            result, status_code = api.execute_custom_queue(custom_config)
            if status_code == 200:
                print(f"   ✅ {result['message']}")
            else:
                print(f"   ❌ Error: {result.get('error', 'Error desconocido')}")

    print("\n🎉 Pruebas completadas!")
    print("\n💡 Consejos:")
    print("   • Puedes usar este script como base para tus propias automatizaciones")
    print("   • Modifica las URLs y parámetros según tus necesidades")
    print("   • Revisa la documentación en la pestaña 'API Server' de la aplicación")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Script interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")