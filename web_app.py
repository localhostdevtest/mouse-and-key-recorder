from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json
import time
import threading
import os
from datetime import datetime
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
from PIL import Image, ImageGrab
import tkinter as tk

class RecorderCore:
    def __init__(self):
        # Variables de estado
        self.is_recording = False
        self.is_playing = False
        self.recorded_events = []
        self.start_time = None
        self.tasks = {}
        self.sequences = {}  # Nueva funcionalidad para secuencias
        self.recording_error = None
        self.listeners_ready = False
        self.is_stopping = False

        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None

        # Controladores para reproducción
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        # Cargar tareas y secuencias
        self.load_tasks_from_file()
        self.load_sequences_from_file()

    def load_tasks_from_file(self):
        """Carga las tareas desde archivo"""
        tasks_file = "tasks.json"
        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
            except Exception as e:
                print(f"Error cargando tareas: {e}")

    def save_tasks_to_file(self):
        """Guarda las tareas en archivo"""
        tasks_file = "tasks.json"
        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando tareas: {e}")
            raise

    def load_sequences_from_file(self):
        """Carga las secuencias desde archivo"""
        sequences_file = "sequences.json"
        if os.path.exists(sequences_file):
            try:
                with open(sequences_file, 'r', encoding='utf-8') as f:
                    self.sequences = json.load(f)
            except Exception as e:
                print(f"Error cargando secuencias: {e}")

    def save_sequences_to_file(self):
        """Guarda las secuencias en archivo"""
        sequences_file = "sequences.json"
        try:
            with open(sequences_file, 'w', encoding='utf-8') as f:
                json.dump(self.sequences, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando secuencias: {e}")

    def create_sequence(self, name, task_names, description="", pause_between=1.0):
        """Crea una nueva secuencia de automatizaciones"""
        # Validar que todas las tareas existen
        missing_tasks = [task for task in task_names if task not in self.tasks]
        if missing_tasks:
            return False, f"Automatizaciones no encontradas: {missing_tasks}"

        sequence = {
            'name': name,
            'description': description,
            'tasks': task_names,
            'pause_between': pause_between,
            'created_at': datetime.now().isoformat(),
            'task_count': len(task_names)
        }

        self.sequences[name] = sequence
        self.save_sequences_to_file()
        return True, f"Secuencia '{name}' creada correctamente"

    def execute_sequence(self, sequence_name):
        """Ejecuta una secuencia de automatizaciones"""
        if sequence_name not in self.sequences:
            return False, f"Secuencia '{sequence_name}' no encontrada"

        def run_sequence():
            try:
                sequence = self.sequences[sequence_name]
                task_names = sequence['tasks']
                pause_time = sequence.get('pause_between', 1.0)

                print(f"Ejecutando secuencia '{sequence_name}' con {len(task_names)} automatizaciones")

                for i, task_name in enumerate(task_names):
                    if task_name not in self.tasks:
                        print(f"Saltando tarea no encontrada: {task_name}")
                        continue

                    print(f"Ejecutando automatización {i+1}/{len(task_names)}: {task_name}")

                    task = self.tasks[task_name]
                    events = task['events']
                    self._execute_events(events)

                    # Pausa entre automatizaciones (excepto después de la última)
                    if i < len(task_names) - 1:
                        time.sleep(pause_time)

                print(f"Secuencia '{sequence_name}' completada")

            except Exception as e:
                print(f"Error ejecutando secuencia: {e}")

        threading.Thread(target=run_sequence, daemon=True).start()
        return True, f"Secuencia '{sequence_name}' iniciada"

    def start_recording(self):
        """Inicia la grabación de eventos"""
        if self.is_recording:
            return False, "Ya se está grabando"

        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()
        self.recording_error = None
        self.listeners_ready = False
        self.is_stopping = False

        # Iniciar listeners en segundo plano para no bloquear la respuesta web
        threading.Thread(target=self._initialize_listeners, daemon=True).start()

        return True, "Grabación iniciada"

    def _initialize_listeners(self):
        """Inicializa listeners de entrada y marca el estado resultante."""
        try:
            self.mouse_listener = MouseListener(
                on_move=self.on_mouse_move,
                on_click=self.on_mouse_click,
                on_scroll=self.on_mouse_scroll
            )
            self.mouse_listener.start()

            self.keyboard_listener = KeyboardListener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.keyboard_listener.start()

            self.listeners_ready = True
            print("Listeners de grabación iniciados correctamente")
        except Exception as e:
            self.recording_error = str(e)
            self.listeners_ready = False
            self.is_recording = False
            print(f"Error iniciando listeners de grabación: {e}")

            try:
                if self.mouse_listener:
                    self.mouse_listener.stop()
            except Exception:
                pass

            try:
                if self.keyboard_listener:
                    self.keyboard_listener.stop()
            except Exception:
                pass

            self.mouse_listener = None
            self.keyboard_listener = None

    def stop_recording(self):
        """Detiene la grabación de eventos"""
        if not self.is_recording:
            return False, "No se está grabando"

        self.is_stopping = True
        self.is_recording = False
        self.listeners_ready = False

        event_count = len(self.recorded_events)

        # Detener listeners en segundo plano para no bloquear la respuesta web
        threading.Thread(target=self._shutdown_listeners, daemon=True).start()

        return True, f"Grabación detenida. {event_count} eventos capturados"

    def _shutdown_listeners(self):
        """Detiene listeners sin bloquear el hilo principal."""
        # Detener listeners de forma más robusta
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
        except Exception as e:
            print(f"Error deteniendo mouse listener: {e}")

        try:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
        except Exception as e:
            print(f"Error deteniendo keyboard listener: {e}")

        self.is_stopping = False
        event_count = len(self.recorded_events)
        print(f"Grabación detenida. Eventos capturados: {event_count}")

    def on_mouse_move(self, x, y):
        if self.is_recording:
            event = {
                'type': 'mouse_move',
                'x': x,
                'y': y,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)

    def on_mouse_click(self, x, y, button, pressed):
        if self.is_recording:
            event = {
                'type': 'mouse_click',
                'x': x,
                'y': y,
                'button': button.name,
                'pressed': pressed,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)

    def on_mouse_scroll(self, x, y, dx, dy):
        if self.is_recording:
            event = {
                'type': 'mouse_scroll',
                'x': x,
                'y': y,
                'dx': dx,
                'dy': dy,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)

    def on_key_press(self, key):
        if self.is_recording:
            try:
                key_name = key.char if hasattr(key, 'char') and key.char else str(key)
            except AttributeError:
                key_name = str(key)

            event = {
                'type': 'key_press',
                'key': key_name,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)

    def on_key_release(self, key):
        if self.is_recording:
            try:
                key_name = key.char if hasattr(key, 'char') and key.char else str(key)
            except AttributeError:
                key_name = str(key)

            event = {
                'type': 'key_release',
                'key': key_name,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)

    def save_task(self, name, description="", prompt_template=""):
        """Guarda la grabación actual como una tarea"""
        if not self.recorded_events:
            return False, "No hay eventos para guardar"

        task = {
            'name': name,
            'description': description,
            'events': self.recorded_events.copy(),
            'created_at': datetime.now().isoformat(),
            'event_count': len(self.recorded_events),
            'prompt_template': prompt_template
        }

        self.tasks[name] = task
        self.save_tasks_to_file()
        return True, f"Tarea '{name}' guardada correctamente"

    def execute_task(self, task_name):
        """Ejecuta una tarea específica"""
        if task_name not in self.tasks:
            return False, f"Tarea '{task_name}' no encontrada"

        def run_task():
            try:
                task = self.tasks[task_name]
                events = task['events']
                self._execute_events(events)
            except Exception as e:
                print(f"Error ejecutando tarea: {e}")

        threading.Thread(target=run_task, daemon=True).start()
        return True, f"Tarea '{task_name}' iniciada"

    def _execute_events(self, events):
        """Ejecuta una lista de eventos"""
        if not events:
            return

        last_time = 0
        for event in events:
            # Esperar el tiempo correcto
            time_diff = event['time'] - last_time
            if time_diff > 0:
                time.sleep(time_diff)
            last_time = event['time']

            # Ejecutar evento
            self._execute_event(event)

    def _execute_event(self, event):
        """Ejecuta un evento específico"""
        try:
            if event['type'] == 'mouse_move':
                self.mouse_controller.position = (event['x'], event['y'])

            elif event['type'] == 'mouse_click':
                button = Button.left if event['button'] == 'left' else Button.right
                if event['pressed']:
                    self.mouse_controller.press(button)
                else:
                    self.mouse_controller.release(button)

            elif event['type'] == 'mouse_scroll':
                self.mouse_controller.scroll(event['dx'], event['dy'])

            elif event['type'] == 'key_press':
                key = self._parse_key(event['key'])
                self.keyboard_controller.press(key)

            elif event['type'] == 'key_release':
                key = self._parse_key(event['key'])
                self.keyboard_controller.release(key)

        except Exception as e:
            print(f"Error ejecutando evento: {e}")

    def _parse_key(self, key_str):
        """Convierte string de tecla a objeto Key"""
        if key_str.startswith('Key.'):
            key_name = key_str.replace('Key.', '')
            return getattr(Key, key_name, key_str)
        else:
            return key_str

    def get_recording_status(self):
        """Devuelve el estado actual de grabación para la API web."""
        return {
            'is_recording': self.is_recording,
            'is_stopping': self.is_stopping,
            'listeners_ready': self.listeners_ready,
            'recording_error': self.recording_error,
            'event_count': len(self.recorded_events)
        }

# Crear instancia global del recorder
recorder = RecorderCore()

# Crear aplicación Flask
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html',
                         is_recording=recorder.is_recording,
                         event_count=len(recorder.recorded_events),
                         task_count=len(recorder.tasks))

@app.route('/docs')
def docs():
    """Página de documentación de API"""
    return render_template('docs.html')

@app.route('/tasks')
def tasks():
    """Página de gestión de tareas"""
    return render_template('tasks.html', tasks=recorder.tasks)

@app.route('/prompts')
def prompts():
    """Página de gestión de prompts"""
    return render_template('prompts.html', tasks=recorder.tasks)

@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    """API para iniciar grabación"""
    success, message = recorder.start_recording()
    return jsonify({
        'success': success,
        'message': message,
        'listeners_ready': recorder.listeners_ready,
        'recording_error': recorder.recording_error
    })

@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    """API para detener grabación"""
    success, message = recorder.stop_recording()
    return jsonify({
        'success': success,
        'message': message,
        'event_count': len(recorder.recorded_events),
        'listeners_ready': recorder.listeners_ready
    })

@app.route('/api/recording/status')
def recording_status():
    """API para obtener estado de grabación"""
    return jsonify(recorder.get_recording_status())

@app.route('/api/tasks/list')
def list_tasks():
    """API para listar todas las tareas"""
    return jsonify({'tasks': recorder.tasks})

@app.route('/api/sequences/list')
def list_sequences():
    """API para listar todas las secuencias"""
    return jsonify({'sequences': recorder.sequences})

@app.route('/api/sequences/create', methods=['POST'])
def create_sequence():
    """API para crear una nueva secuencia"""
    data = request.get_json()
    name = data.get('name', '').strip()
    tasks = data.get('tasks', [])
    description = data.get('description', '').strip()
    pause_between = data.get('pause_between', 1.0)

    if not name:
        return jsonify({'success': False, 'message': 'El nombre es requerido'})

    if not tasks or len(tasks) == 0:
        return jsonify({'success': False, 'message': 'Debe incluir al menos una automatización'})

    success, message = recorder.create_sequence(name, tasks, description, pause_between)
    return jsonify({'success': success, 'message': message})

@app.route('/api/sequences/execute/<sequence_name>', methods=['POST'])
def execute_sequence(sequence_name):
    """API para ejecutar una secuencia"""
    success, message = recorder.execute_sequence(sequence_name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/sequences/delete/<sequence_name>', methods=['DELETE'])
def delete_sequence(sequence_name):
    """API para eliminar una secuencia"""
    if sequence_name in recorder.sequences:
        del recorder.sequences[sequence_name]
        recorder.save_sequences_to_file()
        return jsonify({'success': True, 'message': f'Secuencia "{sequence_name}" eliminada'})
    else:
        return jsonify({'success': False, 'message': 'Secuencia no encontrada'})

# API ULTRA SIMPLE PARA POSTMAN
@app.route('/api/run/<automation_name>', methods=['POST'])
def run_single_automation(automation_name):
    """API súper simple para ejecutar UNA automatización desde Postman"""
    success, message = recorder.execute_task(automation_name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/run-sequence/<sequence_name>', methods=['POST'])
def run_sequence_simple(sequence_name):
    """API súper simple para ejecutar UNA SECUENCIA desde Postman"""
    success, message = recorder.execute_sequence(sequence_name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/quick-sequence', methods=['POST'])
def create_and_run_sequence():
    """API para crear y ejecutar una secuencia al instante"""
    data = request.get_json()
    tasks = data.get('tasks', [])
    pause_between = data.get('pause_between', 1.0)

    if not tasks or len(tasks) == 0:
        return jsonify({'success': False, 'message': 'Debe incluir al menos una automatización'})

    # Validar que todas las tareas existen
    missing_tasks = [task for task in tasks if task not in recorder.tasks]
    if missing_tasks:
        return jsonify({'success': False, 'message': f'Automatizaciones no encontradas: {missing_tasks}'})

    # Ejecutar directamente sin guardar
    def run_quick_sequence():
        try:
            print(f"Ejecutando secuencia rápida con {len(tasks)} automatizaciones")

            for i, task_name in enumerate(tasks):
                print(f"Ejecutando automatización {i+1}/{len(tasks)}: {task_name}")

                task = recorder.tasks[task_name]
                events = task['events']
                recorder._execute_events(events)

                # Pausa entre automatizaciones (excepto después de la última)
                if i < len(tasks) - 1:
                    time.sleep(pause_between)

            print("Secuencia rápida completada")

        except Exception as e:
            print(f"Error ejecutando secuencia rápida: {e}")

    threading.Thread(target=run_quick_sequence, daemon=True).start()
    return jsonify({'success': True, 'message': f'Ejecutando {len(tasks)} automatizaciones en secuencia'})

@app.route('/api/list-all')
def list_everything():
    """API para listar TODO: automatizaciones y secuencias"""
    return jsonify({
        'automations': recorder.tasks,
        'sequences': recorder.sequences,
        'automation_count': len(recorder.tasks),
        'sequence_count': len(recorder.sequences)
    })

@app.route('/api/tasks/save', methods=['POST'])
def save_task():
    """API para guardar tarea"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    prompt_template = data.get('prompt_template', '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'El nombre es requerido'})

    success, message = recorder.save_task(name, description, prompt_template)
    return jsonify({'success': success, 'message': message})

@app.route('/api/tasks/execute/<task_name>', methods=['POST'])
def execute_task(task_name):
    """API para ejecutar tarea"""
    success, message = recorder.execute_task(task_name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/tasks/delete/<task_name>', methods=['DELETE'])
def delete_task(task_name):
    """API para eliminar tarea"""
    task = recorder.tasks.get(task_name)
    if task is None:
        return jsonify({'success': False, 'message': 'Tarea no encontrada'}), 404

    del recorder.tasks[task_name]

    try:
        recorder.save_tasks_to_file()
    except Exception:
        recorder.tasks[task_name] = task
        return jsonify({
            'success': False,
            'message': f'No se pudo eliminar la tarea "{task_name}"'
        }), 500

    return jsonify({'success': True, 'message': f'Tarea "{task_name}" eliminada'})

@app.route('/api/tasks/update/<task_name>', methods=['PUT'])
def update_task(task_name):
    """API para actualizar tarea"""
    if task_name not in recorder.tasks:
        return jsonify({'success': False, 'message': 'Tarea no encontrada'})

    data = request.get_json()
    task = recorder.tasks[task_name]

    if 'description' in data:
        task['description'] = data['description']
    if 'prompt_template' in data:
        task['prompt_template'] = data['prompt_template']

    recorder.save_tasks_to_file()
    return jsonify({'success': True, 'message': 'Tarea actualizada'})

@app.route('/api/prompts/generate', methods=['POST'])
def generate_prompt():
    """API para generar prompt final"""
    data = request.get_json()
    task_name = data.get('task_name')
    dynamic_content = data.get('dynamic_content', '')

    if task_name not in recorder.tasks:
        return jsonify({'success': False, 'message': 'Tarea no encontrada'})

    task = recorder.tasks[task_name]
    prompt_template = task.get('prompt_template', '')

    if not prompt_template:
        return jsonify({'success': False, 'message': 'Esta tarea no tiene prompt configurado'})

    # Generar prompt final
    if '{CONTENIDO_DINAMICO}' in prompt_template:
        final_prompt = prompt_template.replace('{CONTENIDO_DINAMICO}', dynamic_content)
    else:
        final_prompt = prompt_template
        if dynamic_content:
            final_prompt += f"\n\nContenido adicional:\n{dynamic_content}"

    return jsonify({'success': True, 'final_prompt': final_prompt})

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
