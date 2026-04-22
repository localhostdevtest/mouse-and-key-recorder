import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
import os
from PIL import Image, ImageTk, ImageGrab
from datetime import datetime
from flask import Flask, request, jsonify
import socket

class AreaSelector:
    def __init__(self, parent_callback):
        self.parent_callback = parent_callback
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.rect_id = None

        # Crear ventana overlay transparente
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')
        self.overlay.overrideredirect(True)

        # Canvas para dibujar la selección
        self.canvas = tk.Canvas(self.overlay, highlightthickness=0, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bindings para mouse
        self.canvas.bind('<Button-1>', self.start_selection)
        self.canvas.bind('<B1-Motion>', self.update_selection)
        self.canvas.bind('<ButtonRelease-1>', self.end_selection)
        self.canvas.bind('<Escape>', self.cancel_selection)

        # Instrucciones
        self.canvas.create_text(
            self.overlay.winfo_screenwidth() // 2,
            50,
            text="Haz clic y arrastra para seleccionar el área a capturar\nPresiona ESC para cancelar",
            fill='white',
            font=('Arial', 16),
            justify=tk.CENTER
        )

        self.overlay.focus_set()

    def start_selection(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def update_selection(self, event):
        if self.start_x is not None and self.start_y is not None:
            if self.rect_id:
                self.canvas.delete(self.rect_id)

            self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline='red', width=2, fill='', stipple='gray50'
            )

    def end_selection(self, event):
        if self.start_x is not None and self.start_y is not None:
            self.end_x = event.x
            self.end_y = event.y

            # Asegurar que las coordenadas estén en el orden correcto
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)

            # Cerrar overlay antes de capturar
            self.overlay.destroy()

            # Capturar área seleccionada
            self.capture_area(x1, y1, x2, y2)

    def cancel_selection(self, event):
        self.overlay.destroy()

    def capture_area(self, x1, y1, x2, y2):
        try:
            # Pequeña pausa para asegurar que el overlay se cierre completamente
            time.sleep(0.1)

            # Capturar el área seleccionada
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))

            # Generar nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

            # Crear directorio screenshots si no existe
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)

            filepath = os.path.join(screenshots_dir, filename)
            screenshot.save(filepath)

            # Notificar al parent
            self.parent_callback(filepath, screenshot)

        except Exception as e:
            messagebox.showerror("Error", f"Error al capturar screenshot: {str(e)}")

class HTTPServer:
    def __init__(self, recorder_instance):
        self.recorder = recorder_instance
        self.app = Flask(__name__)
        self.server_thread = None
        self.is_running = False
        self.port = 8080

        # Configurar rutas
        self.setup_routes()

        # Desactivar logs de Flask para mantener la consola limpia
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

    def setup_routes(self):
        """Configura las rutas del servidor HTTP"""

        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Obtiene el estado del servidor y las tareas"""
            return jsonify({
                'status': 'running',
                'tasks_count': len(self.recorder.tasks),
                'server_port': self.port,
                'available_endpoints': [
                    'GET /api/status',
                    'GET /api/tasks',
                    'POST /api/execute/task',
                    'POST /api/execute/queue',
                    'POST /api/execute/custom-queue'
                ]
            })

        @self.app.route('/api/tasks', methods=['GET'])
        def get_tasks():
            """Lista todas las tareas disponibles"""
            tasks_info = {}
            for name, task in self.recorder.tasks.items():
                tasks_info[name] = {
                    'name': task['name'],
                    'description': task.get('description', ''),
                    'event_count': task['event_count'],
                    'created_at': task['created_at']
                }

            return jsonify({
                'tasks': tasks_info,
                'count': len(tasks_info)
            })

        @self.app.route('/api/execute/task', methods=['POST'])
        def execute_task():
            """Ejecuta una tarea específica"""
            try:
                data = request.get_json()
                if not data or 'task_name' not in data:
                    return jsonify({'error': 'task_name is required'}), 400

                task_name = data['task_name']

                if task_name not in self.recorder.tasks:
                    return jsonify({'error': f'Task "{task_name}" not found'}), 404

                # Ejecutar tarea en hilo separado
                def execute():
                    self.recorder._execute_single_task(task_name)

                threading.Thread(target=execute, daemon=True).start()

                return jsonify({
                    'message': f'Task "{task_name}" started successfully',
                    'task_name': task_name
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/execute/queue', methods=['POST'])
        def execute_predefined_queue():
            """Ejecuta una cola predefinida de tareas"""
            try:
                data = request.get_json()
                if not data or 'tasks' not in data:
                    return jsonify({'error': 'tasks array is required'}), 400

                task_names = data['tasks']
                pause_time = data.get('pause_time', 1.0)
                repeat_mode = data.get('repeat', False)

                # Validar que todas las tareas existen
                missing_tasks = [name for name in task_names if name not in self.recorder.tasks]
                if missing_tasks:
                    return jsonify({'error': f'Tasks not found: {missing_tasks}'}), 404

                # Ejecutar cola en hilo separado
                def execute():
                    self.recorder._execute_task_queue(task_names, pause_time, repeat_mode)

                threading.Thread(target=execute, daemon=True).start()

                return jsonify({
                    'message': f'Queue with {len(task_names)} tasks started successfully',
                    'tasks': task_names,
                    'pause_time': pause_time,
                    'repeat_mode': repeat_mode
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/execute/custom-queue', methods=['POST'])
        def execute_custom_queue():
            """Ejecuta una cola personalizada con configuración avanzada"""
            try:
                data = request.get_json()
                if not data or 'queue' not in data:
                    return jsonify({'error': 'queue configuration is required'}), 400

                queue_config = data['queue']

                # Validar configuración de cola
                if 'tasks' not in queue_config:
                    return jsonify({'error': 'tasks array is required in queue'}), 400

                tasks = queue_config['tasks']
                global_pause = queue_config.get('global_pause_time', 1.0)
                repeat_mode = queue_config.get('repeat', False)
                repeat_count = queue_config.get('repeat_count', 0)  # 0 = infinito

                # Procesar tareas con configuración individual
                processed_tasks = []
                for task_item in tasks:
                    if isinstance(task_item, str):
                        # Tarea simple
                        if task_item not in self.recorder.tasks:
                            return jsonify({'error': f'Task "{task_item}" not found'}), 404
                        processed_tasks.append({
                            'name': task_item,
                            'pause_after': global_pause
                        })
                    elif isinstance(task_item, dict):
                        # Tarea con configuración
                        task_name = task_item.get('name')
                        if not task_name or task_name not in self.recorder.tasks:
                            return jsonify({'error': f'Task "{task_name}" not found'}), 404
                        processed_tasks.append({
                            'name': task_name,
                            'pause_after': task_item.get('pause_after', global_pause),
                            'repeat_task': task_item.get('repeat_task', 1)
                        })

                # Ejecutar cola personalizada
                def execute():
                    self.recorder._execute_custom_queue(processed_tasks, repeat_mode, repeat_count)

                threading.Thread(target=execute, daemon=True).start()

                return jsonify({
                    'message': f'Custom queue with {len(processed_tasks)} tasks started successfully',
                    'queue_config': queue_config
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def find_available_port(self, start_port=8080):
        """Encuentra un puerto disponible"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return None

    def start_server(self):
        """Inicia el servidor HTTP"""
        if self.is_running:
            return False, "Server is already running"

        # Encontrar puerto disponible
        available_port = self.find_available_port(self.port)
        if not available_port:
            return False, "No available ports found"

        self.port = available_port

        def run_server():
            try:
                self.app.run(host='localhost', port=self.port, debug=False, use_reloader=False)
            except Exception as e:
                print(f"Server error: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

        return True, f"Server started on http://localhost:{self.port}"

    def stop_server(self):
        """Detiene el servidor HTTP"""
        if not self.is_running:
            return False, "Server is not running"

        # Flask no tiene una forma limpia de detener el servidor desde otro hilo
        # En un entorno de producción usarías un servidor WSGI apropiado
        self.is_running = False
        return True, "Server stop requested"

class MouseKeyboardRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Grabador de Mouse y Teclado - Gestor de Tareas")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # Variables de estado
        self.is_recording = False
        self.is_playing = False
        self.recorded_events = []
        self.start_time = None
        self.last_screenshot = None

        # Sistema de tareas
        self.tasks = {}  # Diccionario de tareas guardadas
        self.current_task_name = ""

        # Servidor HTTP
        self.http_server = HTTPServer(self)
        self.server_status = "stopped"

        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None

        # Controladores para reproducción
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.setup_ui()

    def setup_ui(self):
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Pestaña 1: Grabación
        self.recording_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.recording_frame, text="🔴 Grabación")
        self.setup_recording_tab()

        # Pestaña 2: Gestión de Tareas
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="📋 Tareas")
        self.setup_tasks_tab()

        # Pestaña 3: Servidor HTTP
        self.server_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.server_frame, text="🌐 API Server")
        self.setup_server_tab()

        # Pestaña 4: Captura de Pantalla
        self.screenshot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.screenshot_frame, text="📸 Screenshots")
        self.setup_screenshot_tab()

        # Cargar tareas guardadas al inicio
        self.load_tasks_from_file()

    def setup_recording_tab(self):
        """Configura la pestaña de grabación"""
        main_frame = ttk.Frame(self.recording_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Grabador de Mouse y Teclado",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Frame para botones principales
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        self.record_btn = ttk.Button(buttons_frame, text="🔴 Grabar",
                                   command=self.start_recording, width=15)
        self.record_btn.grid(row=0, column=0, padx=5, pady=5)

        self.stop_btn = ttk.Button(buttons_frame, text="⏹️ Parar",
                                 command=self.stop_recording, width=15, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5)

        self.play_btn = ttk.Button(buttons_frame, text="▶️ Reproducir",
                                 command=self.play_recording, width=15, state="disabled")
        self.play_btn.grid(row=1, column=0, padx=5, pady=5)

        self.clear_btn = ttk.Button(buttons_frame, text="🗑️ Limpiar",
                                  command=self.clear_recording, width=15)
        self.clear_btn.grid(row=1, column=1, padx=5, pady=5)

        # Separador
        separator1 = ttk.Separator(main_frame, orient='horizontal')
        separator1.pack(fill=tk.X, pady=20)

        # Frame para guardar como tarea
        task_frame = ttk.LabelFrame(main_frame, text="Guardar como Tarea", padding="10")
        task_frame.pack(fill=tk.X, pady=10)

        ttk.Label(task_frame, text="Nombre de la tarea:").pack(anchor=tk.W)
        self.task_name_entry = ttk.Entry(task_frame, width=40)
        self.task_name_entry.pack(fill=tk.X, pady=(5, 10))

        ttk.Label(task_frame, text="Descripción (opcional):").pack(anchor=tk.W)
        self.task_desc_entry = ttk.Entry(task_frame, width=40)
        self.task_desc_entry.pack(fill=tk.X, pady=(5, 10))

        self.save_task_btn = ttk.Button(task_frame, text="💾 Guardar como Tarea",
                                      command=self.save_as_task, state="disabled")
        self.save_task_btn.pack()

        # Separador
        separator2 = ttk.Separator(main_frame, orient='horizontal')
        separator2.pack(fill=tk.X, pady=20)

        # Botones de archivo (grabaciones individuales)
        file_frame = ttk.LabelFrame(main_frame, text="Archivos de Grabación", padding="10")
        file_frame.pack(fill=tk.X, pady=10)

        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack()

        self.save_btn = ttk.Button(file_buttons_frame, text="💾 Guardar Grabación",
                                 command=self.save_recording, width=20)
        self.save_btn.grid(row=0, column=0, padx=5, pady=5)

        self.load_btn = ttk.Button(file_buttons_frame, text="📁 Cargar Grabación",
                                 command=self.load_recording, width=20)
        self.load_btn.grid(row=0, column=1, padx=5, pady=5)

        # Estado
        self.status_label = ttk.Label(main_frame, text="Listo para grabar",
                                    font=("Arial", 10))
        self.status_label.pack(pady=(20, 5))

        # Información de eventos
        self.events_label = ttk.Label(main_frame, text="Eventos grabados: 0",
                                    font=("Arial", 9))
        self.events_label.pack(pady=5)

    def setup_tasks_tab(self):
        """Configura la pestaña de gestión de tareas"""
        main_frame = ttk.Frame(self.tasks_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Gestión de Tareas",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Frame principal con dos columnas
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Columna izquierda - Lista de tareas
        left_frame = ttk.LabelFrame(content_frame, text="Tareas Disponibles", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Listbox con scrollbar para tareas
        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.tasks_listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, height=15)
        scrollbar_tasks = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.tasks_listbox.yview)
        self.tasks_listbox.configure(yscrollcommand=scrollbar_tasks.set)

        self.tasks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_tasks.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones para gestión de tareas
        task_buttons_frame = ttk.Frame(left_frame)
        task_buttons_frame.pack(fill=tk.X, pady=(10, 0))

        self.delete_task_btn = ttk.Button(task_buttons_frame, text="🗑️ Eliminar",
                                        command=self.delete_selected_tasks, width=12)
        self.delete_task_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.edit_task_btn = ttk.Button(task_buttons_frame, text="✏️ Editar",
                                      command=self.edit_selected_task, width=12)
        self.edit_task_btn.pack(side=tk.LEFT, padx=5)

        self.duplicate_task_btn = ttk.Button(task_buttons_frame, text="📋 Duplicar",
                                           command=self.duplicate_selected_task, width=12)
        self.duplicate_task_btn.pack(side=tk.LEFT, padx=5)

        # Columna derecha - Ejecución de tareas
        right_frame = ttk.LabelFrame(content_frame, text="Ejecución de Tareas", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Lista de tareas seleccionadas para ejecutar
        ttk.Label(right_frame, text="Cola de Ejecución:", font=("Arial", 12, "bold")).pack(anchor=tk.W)

        queue_frame = ttk.Frame(right_frame)
        queue_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.queue_listbox = tk.Listbox(queue_frame, height=10)
        scrollbar_queue = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_listbox.yview)
        self.queue_listbox.configure(yscrollcommand=scrollbar_queue.set)

        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_queue.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones para gestión de cola
        queue_buttons_frame = ttk.Frame(right_frame)
        queue_buttons_frame.pack(fill=tk.X, pady=(5, 10))

        self.add_to_queue_btn = ttk.Button(queue_buttons_frame, text="➕ Agregar a Cola",
                                         command=self.add_to_queue, width=15)
        self.add_to_queue_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.remove_from_queue_btn = ttk.Button(queue_buttons_frame, text="➖ Quitar de Cola",
                                              command=self.remove_from_queue, width=15)
        self.remove_from_queue_btn.pack(side=tk.LEFT, padx=5)

        self.clear_queue_btn = ttk.Button(queue_buttons_frame, text="🗑️ Limpiar Cola",
                                        command=self.clear_queue, width=15)
        self.clear_queue_btn.pack(side=tk.LEFT, padx=5)

        # Botones de ejecución
        execution_frame = ttk.LabelFrame(right_frame, text="Ejecución", padding="10")
        execution_frame.pack(fill=tk.X, pady=(10, 0))

        self.run_queue_btn = ttk.Button(execution_frame, text="▶️ Ejecutar Cola",
                                      command=self.run_task_queue, width=20)
        self.run_queue_btn.pack(pady=5)

        self.run_selected_btn = ttk.Button(execution_frame, text="▶️ Ejecutar Seleccionada",
                                         command=self.run_selected_task, width=20)
        self.run_selected_btn.pack(pady=5)

        # Configuración de ejecución
        config_frame = ttk.LabelFrame(right_frame, text="Configuración", padding="10")
        config_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(config_frame, text="Pausa entre tareas (segundos):").pack(anchor=tk.W)
        self.pause_var = tk.StringVar(value="1.0")
        self.pause_entry = ttk.Entry(config_frame, textvariable=self.pause_var, width=10)
        self.pause_entry.pack(anchor=tk.W, pady=(5, 10))

        self.repeat_var = tk.BooleanVar()
        self.repeat_checkbox = ttk.Checkbutton(config_frame, text="Repetir cola continuamente",
                                             variable=self.repeat_var)
        self.repeat_checkbox.pack(anchor=tk.W)

        # Estado de ejecución
        self.execution_status_label = ttk.Label(right_frame, text="Listo para ejecutar",
                                              font=("Arial", 10))
        self.execution_status_label.pack(pady=(10, 0))

    def setup_server_tab(self):
        """Configura la pestaña del servidor HTTP"""
        main_frame = ttk.Frame(self.server_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Servidor API HTTP",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Estado del servidor
        status_frame = ttk.LabelFrame(main_frame, text="Estado del Servidor", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 20))

        self.server_status_label = ttk.Label(status_frame, text="🔴 Servidor detenido",
                                           font=("Arial", 12))
        self.server_status_label.pack(pady=5)

        self.server_url_label = ttk.Label(status_frame, text="",
                                        font=("Arial", 10), foreground="blue")
        self.server_url_label.pack(pady=5)

        # Controles del servidor
        controls_frame = ttk.Frame(status_frame)
        controls_frame.pack(pady=10)

        self.start_server_btn = ttk.Button(controls_frame, text="🚀 Iniciar Servidor",
                                         command=self.start_http_server, width=20)
        self.start_server_btn.pack(side=tk.LEFT, padx=5)

        self.stop_server_btn = ttk.Button(controls_frame, text="⏹️ Detener Servidor",
                                        command=self.stop_http_server, width=20, state="disabled")
        self.stop_server_btn.pack(side=tk.LEFT, padx=5)

        # Documentación de la API
        api_frame = ttk.LabelFrame(main_frame, text="Documentación de la API", padding="15")
        api_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Crear un widget de texto con scrollbar para la documentación
        doc_frame = ttk.Frame(api_frame)
        doc_frame.pack(fill=tk.BOTH, expand=True)

        self.api_doc_text = tk.Text(doc_frame, wrap=tk.WORD, height=20, font=("Consolas", 9))
        scrollbar_doc = ttk.Scrollbar(doc_frame, orient=tk.VERTICAL, command=self.api_doc_text.yview)
        self.api_doc_text.configure(yscrollcommand=scrollbar_doc.set)

        self.api_doc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_doc.pack(side=tk.RIGHT, fill=tk.Y)

        # Insertar documentación
        self.insert_api_documentation()

        # Botones de utilidad
        utils_frame = ttk.Frame(main_frame)
        utils_frame.pack(fill=tk.X, pady=10)

        self.copy_examples_btn = ttk.Button(utils_frame, text="📋 Copiar Ejemplos",
                                          command=self.copy_api_examples, width=20)
        self.copy_examples_btn.pack(side=tk.LEFT, padx=5)

        self.test_api_btn = ttk.Button(utils_frame, text="🧪 Probar API",
                                     command=self.test_api_connection, width=20)
        self.test_api_btn.pack(side=tk.LEFT, padx=5)

    def insert_api_documentation(self):
        """Inserta la documentación de la API en el widget de texto"""
        doc_text = """
🌐 DOCUMENTACIÓN DE LA API HTTP

El servidor HTTP permite ejecutar tareas y colas mediante peticiones POST.
Base URL: http://localhost:PUERTO (el puerto se muestra cuando el servidor está activo)

═══════════════════════════════════════════════════════════════════════════════

📋 ENDPOINTS DISPONIBLES:

1. GET /api/status
   Obtiene el estado del servidor y información general

   Respuesta:
   {
     "status": "running",
     "tasks_count": 5,
     "server_port": 8080,
     "available_endpoints": [...]
   }

2. GET /api/tasks
   Lista todas las tareas disponibles

   Respuesta:
   {
     "tasks": {
       "tarea1": {
         "name": "tarea1",
         "description": "Descripción de la tarea",
         "event_count": 15,
         "created_at": "2024-04-22T10:30:00"
       }
     },
     "count": 1
   }

3. POST /api/execute/task
   Ejecuta una tarea específica

   Body:
   {
     "task_name": "nombre_de_la_tarea"
   }

   Respuesta:
   {
     "message": "Task 'nombre_de_la_tarea' started successfully",
     "task_name": "nombre_de_la_tarea"
   }

4. POST /api/execute/queue
   Ejecuta una cola simple de tareas

   Body:
   {
     "tasks": ["tarea1", "tarea2", "tarea3"],
     "pause_time": 2.0,
     "repeat": false
   }

   Respuesta:
   {
     "message": "Queue with 3 tasks started successfully",
     "tasks": ["tarea1", "tarea2", "tarea3"],
     "pause_time": 2.0,
     "repeat_mode": false
   }

5. POST /api/execute/custom-queue
   Ejecuta una cola personalizada con configuración avanzada

   Body:
   {
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
   }

═══════════════════════════════════════════════════════════════════════════════

💡 EJEMPLOS DE USO:

# Usando curl (desde terminal):

# Obtener estado del servidor
curl http://localhost:8080/api/status

# Listar tareas
curl http://localhost:8080/api/tasks

# Ejecutar una tarea
curl -X POST http://localhost:8080/api/execute/task \\
     -H "Content-Type: application/json" \\
     -d '{"task_name": "mi_tarea"}'

# Ejecutar cola simple
curl -X POST http://localhost:8080/api/execute/queue \\
     -H "Content-Type: application/json" \\
     -d '{"tasks": ["tarea1", "tarea2"], "pause_time": 1.5}'

# Usando Python:
import requests

# Ejecutar tarea
response = requests.post('http://localhost:8080/api/execute/task',
                        json={'task_name': 'mi_tarea'})
print(response.json())

# Ejecutar cola
response = requests.post('http://localhost:8080/api/execute/queue',
                        json={
                            'tasks': ['tarea1', 'tarea2'],
                            'pause_time': 2.0,
                            'repeat': False
                        })
print(response.json())

═══════════════════════════════════════════════════════════════════════════════

⚠️ NOTAS IMPORTANTES:

• El servidor se ejecuta en localhost únicamente por seguridad
• Las tareas se ejecutan de forma asíncrona
• Los nombres de tareas son case-sensitive
• El servidor encuentra automáticamente un puerto disponible
• Todas las respuestas son en formato JSON
• Los errores devuelven códigos HTTP apropiados (400, 404, 500)

═══════════════════════════════════════════════════════════════════════════════
"""
        self.api_doc_text.insert(tk.END, doc_text)
        self.api_doc_text.config(state=tk.DISABLED)  # Solo lectura

    def setup_screenshot_tab(self):
        """Configura la pestaña de captura de pantalla"""
        main_frame = ttk.Frame(self.screenshot_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Captura de Pantalla",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Botón de captura de área
        self.screenshot_btn = ttk.Button(main_frame, text="📸 Capturar Área",
                                       command=self.start_area_capture, width=25)
        self.screenshot_btn.pack(pady=20)

        # Información del último screenshot
        self.screenshot_label = ttk.Label(main_frame, text="",
                                        font=("Arial", 10), foreground="blue")
        self.screenshot_label.pack(pady=10)

    def start_recording(self):
        """Inicia la grabación de eventos"""
        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()

        # Actualizar UI
        self.record_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.play_btn.config(state="disabled")
        self.status_label.config(text="🔴 Grabando... (Presiona PARAR para terminar)")
        self.events_label.config(text="Eventos grabados: 0")

        # Iniciar listeners
        self.start_listeners()

    def stop_recording(self):
        """Detiene la grabación de eventos"""
        self.is_recording = False

        # Detener listeners
        self.stop_listeners()

        # Actualizar UI
        self.record_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.recorded_events:
            self.play_btn.config(state="normal")
            self.save_task_btn.config(state="normal")
            self.status_label.config(text="✅ Grabación completada")
        else:
            self.status_label.config(text="⚠️ No se grabaron eventos")

        self.events_label.config(text=f"Eventos grabados: {len(self.recorded_events)}")

    def start_listeners(self):
        """Inicia los listeners de mouse y teclado"""
        # Mouse listener
        self.mouse_listener = MouseListener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click,
            on_scroll=self.on_mouse_scroll
        )
        self.mouse_listener.start()

        # Keyboard listener
        self.keyboard_listener = KeyboardListener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.keyboard_listener.start()

    def stop_listeners(self):
        """Detiene los listeners"""
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()

    def on_mouse_move(self, x, y):
        """Maneja el movimiento del mouse"""
        if self.is_recording:
            event = {
                'type': 'mouse_move',
                'x': x,
                'y': y,
                'time': time.time() - self.start_time
            }
            self.recorded_events.append(event)
            self.update_events_count()

    def on_mouse_click(self, x, y, button, pressed):
        """Maneja los clics del mouse"""
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
            self.update_events_count()

    def on_mouse_scroll(self, x, y, dx, dy):
        """Maneja el scroll del mouse"""
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
            self.update_events_count()

    def on_key_press(self, key):
        """Maneja las teclas presionadas"""
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
            self.update_events_count()

    def on_key_release(self, key):
        """Maneja las teclas liberadas"""
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
            self.update_events_count()

    def update_events_count(self):
        """Actualiza el contador de eventos en la UI"""
        self.root.after(0, lambda: self.events_label.config(
            text=f"Eventos grabados: {len(self.recorded_events)}"))

    # ==================== MÉTODOS DE GESTIÓN DE TAREAS ====================

    def save_as_task(self):
        """Guarda la grabación actual como una tarea"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabación para guardar como tarea")
            return

        task_name = self.task_name_entry.get().strip()
        if not task_name:
            messagebox.showwarning("Advertencia", "Por favor ingresa un nombre para la tarea")
            return

        if task_name in self.tasks:
            if not messagebox.askyesno("Confirmar", f"La tarea '{task_name}' ya existe. ¿Deseas sobrescribirla?"):
                return

        task_description = self.task_desc_entry.get().strip()

        # Crear objeto tarea
        task = {
            'name': task_name,
            'description': task_description,
            'events': self.recorded_events.copy(),
            'created_at': datetime.now().isoformat(),
            'event_count': len(self.recorded_events)
        }

        # Guardar tarea
        self.tasks[task_name] = task
        self.save_tasks_to_file()
        self.refresh_tasks_list()

        # Limpiar campos
        self.task_name_entry.delete(0, tk.END)
        self.task_desc_entry.delete(0, tk.END)

        messagebox.showinfo("Éxito", f"Tarea '{task_name}' guardada correctamente")

    def load_tasks_from_file(self):
        """Carga las tareas desde archivo"""
        tasks_file = "tasks.json"
        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
                self.refresh_tasks_list()
            except Exception as e:
                print(f"Error cargando tareas: {e}")

    def save_tasks_to_file(self):
        """Guarda las tareas en archivo"""
        tasks_file = "tasks.json"
        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando tareas: {str(e)}")

    def refresh_tasks_list(self):
        """Actualiza la lista de tareas en la UI"""
        self.tasks_listbox.delete(0, tk.END)
        for task_name, task_data in self.tasks.items():
            display_text = f"{task_name} ({task_data['event_count']} eventos)"
            if task_data.get('description'):
                display_text += f" - {task_data['description']}"
            self.tasks_listbox.insert(tk.END, display_text)

    def delete_selected_tasks(self):
        """Elimina las tareas seleccionadas"""
        selected_indices = self.tasks_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos una tarea para eliminar")
            return

        task_names = list(self.tasks.keys())
        selected_tasks = [task_names[i] for i in selected_indices]

        if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar {len(selected_tasks)} tarea(s)?"):
            for task_name in selected_tasks:
                del self.tasks[task_name]

            self.save_tasks_to_file()
            self.refresh_tasks_list()
            messagebox.showinfo("Éxito", f"{len(selected_tasks)} tarea(s) eliminada(s)")

    def edit_selected_task(self):
        """Edita la tarea seleccionada"""
        selected_indices = self.tasks_listbox.curselection()
        if len(selected_indices) != 1:
            messagebox.showwarning("Advertencia", "Selecciona exactamente una tarea para editar")
            return

        task_names = list(self.tasks.keys())
        task_name = task_names[selected_indices[0]]
        task = self.tasks[task_name]

        # Crear ventana de edición
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Editar Tarea: {task_name}")
        edit_window.geometry("400x300")
        edit_window.transient(self.root)
        edit_window.grab_set()

        # Campos de edición
        ttk.Label(edit_window, text="Nombre:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=20, pady=(20, 5))
        name_var = tk.StringVar(value=task_name)
        name_entry = ttk.Entry(edit_window, textvariable=name_var, width=50)
        name_entry.pack(padx=20, pady=(0, 10))

        ttk.Label(edit_window, text="Descripción:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=20, pady=(10, 5))
        desc_var = tk.StringVar(value=task.get('description', ''))
        desc_entry = ttk.Entry(edit_window, textvariable=desc_var, width=50)
        desc_entry.pack(padx=20, pady=(0, 10))

        # Información de la tarea
        info_frame = ttk.LabelFrame(edit_window, text="Información", padding="10")
        info_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(info_frame, text=f"Eventos: {task['event_count']}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Creada: {task['created_at'][:19]}").pack(anchor=tk.W)

        # Botones
        buttons_frame = ttk.Frame(edit_window)
        buttons_frame.pack(pady=20)

        def save_changes():
            new_name = name_var.get().strip()
            new_desc = desc_var.get().strip()

            if not new_name:
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacío")
                return

            if new_name != task_name and new_name in self.tasks:
                messagebox.showwarning("Advertencia", "Ya existe una tarea con ese nombre")
                return

            # Actualizar tarea
            if new_name != task_name:
                self.tasks[new_name] = self.tasks.pop(task_name)
                task_name_updated = new_name
            else:
                task_name_updated = task_name

            self.tasks[task_name_updated]['name'] = new_name
            self.tasks[task_name_updated]['description'] = new_desc

            self.save_tasks_to_file()
            self.refresh_tasks_list()
            edit_window.destroy()
            messagebox.showinfo("Éxito", "Tarea actualizada correctamente")

        ttk.Button(buttons_frame, text="💾 Guardar", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="❌ Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)

    def duplicate_selected_task(self):
        """Duplica la tarea seleccionada"""
        selected_indices = self.tasks_listbox.curselection()
        if len(selected_indices) != 1:
            messagebox.showwarning("Advertencia", "Selecciona exactamente una tarea para duplicar")
            return

        task_names = list(self.tasks.keys())
        original_name = task_names[selected_indices[0]]
        original_task = self.tasks[original_name]

        # Generar nuevo nombre
        counter = 1
        new_name = f"{original_name}_copia"
        while new_name in self.tasks:
            counter += 1
            new_name = f"{original_name}_copia_{counter}"

        # Crear tarea duplicada
        new_task = original_task.copy()
        new_task['name'] = new_name
        new_task['created_at'] = datetime.now().isoformat()
        new_task['events'] = original_task['events'].copy()

        self.tasks[new_name] = new_task
        self.save_tasks_to_file()
        self.refresh_tasks_list()

        messagebox.showinfo("Éxito", f"Tarea duplicada como '{new_name}'")

    def add_to_queue(self):
        """Agrega tareas seleccionadas a la cola de ejecución"""
        selected_indices = self.tasks_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos una tarea para agregar a la cola")
            return

        task_names = list(self.tasks.keys())
        for index in selected_indices:
            task_name = task_names[index]
            # Evitar duplicados en la cola
            items = [self.queue_listbox.get(i) for i in range(self.queue_listbox.size())]
            if task_name not in items:
                self.queue_listbox.insert(tk.END, task_name)

    def remove_from_queue(self):
        """Quita tareas seleccionadas de la cola de ejecución"""
        selected_indices = self.queue_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos una tarea para quitar de la cola")
            return

        # Eliminar en orden inverso para mantener índices válidos
        for index in reversed(selected_indices):
            self.queue_listbox.delete(index)

    def clear_queue(self):
        """Limpia toda la cola de ejecución"""
        if self.queue_listbox.size() > 0:
            if messagebox.askyesno("Confirmar", "¿Estás seguro de limpiar toda la cola?"):
                self.queue_listbox.delete(0, tk.END)

    def run_selected_task(self):
        """Ejecuta la tarea seleccionada inmediatamente"""
        selected_indices = self.tasks_listbox.curselection()
        if len(selected_indices) != 1:
            messagebox.showwarning("Advertencia", "Selecciona exactamente una tarea para ejecutar")
            return

        task_names = list(self.tasks.keys())
        task_name = task_names[selected_indices[0]]

        self.execution_status_label.config(text=f"Ejecutando: {task_name}")
        threading.Thread(target=self._execute_single_task, args=(task_name,), daemon=True).start()

    def run_task_queue(self):
        """Ejecuta todas las tareas en la cola"""
        if self.queue_listbox.size() == 0:
            messagebox.showwarning("Advertencia", "La cola está vacía")
            return

        queue_tasks = [self.queue_listbox.get(i) for i in range(self.queue_listbox.size())]
        pause_time = float(self.pause_var.get())
        repeat_mode = self.repeat_var.get()

        self.execution_status_label.config(text="Ejecutando cola...")
        threading.Thread(target=self._execute_task_queue, args=(queue_tasks, pause_time, repeat_mode), daemon=True).start()

    def _execute_single_task(self, task_name):
        """Ejecuta una sola tarea"""
        try:
            if task_name not in self.tasks:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Tarea '{task_name}' no encontrada"))
                return

            task = self.tasks[task_name]
            events = task['events']

            self._execute_events(events)

            self.root.after(0, lambda: self.execution_status_label.config(text="✅ Tarea completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando tarea: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="❌ Error en ejecución"))

    def _execute_task_queue(self, queue_tasks, pause_time, repeat_mode):
        """Ejecuta la cola de tareas"""
        try:
            cycle_count = 1
            while True:
                self.root.after(0, lambda c=cycle_count: self.execution_status_label.config(
                    text=f"Ejecutando cola - Ciclo {c}" if repeat_mode else "Ejecutando cola"))

                for i, task_name in enumerate(queue_tasks):
                    if task_name not in self.tasks:
                        continue

                    self.root.after(0, lambda t=task_name, idx=i: self.execution_status_label.config(
                        text=f"Ejecutando: {t} ({idx+1}/{len(queue_tasks)})"))

                    task = self.tasks[task_name]
                    events = task['events']
                    self._execute_events(events)

                    # Pausa entre tareas (excepto después de la última)
                    if i < len(queue_tasks) - 1:
                        time.sleep(pause_time)

                if not repeat_mode:
                    break

                cycle_count += 1
                # Pausa antes del siguiente ciclo
                time.sleep(pause_time)

            self.root.after(0, lambda: self.execution_status_label.config(text="✅ Cola completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando cola: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="❌ Error en ejecución"))

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

    def _execute_custom_queue(self, processed_tasks, repeat_mode, repeat_count):
        """Ejecuta una cola personalizada con configuración avanzada"""
        try:
            cycle = 0
            while True:
                cycle += 1

                if repeat_count > 0 and cycle > repeat_count:
                    break

                self.root.after(0, lambda c=cycle: self.execution_status_label.config(
                    text=f"Ejecutando cola personalizada - Ciclo {c}"))

                for i, task_config in enumerate(processed_tasks):
                    task_name = task_config['name']
                    repeat_task = task_config.get('repeat_task', 1)
                    pause_after = task_config.get('pause_after', 1.0)

                    if task_name not in self.tasks:
                        continue

                    # Repetir la tarea individual si es necesario
                    for rep in range(repeat_task):
                        self.root.after(0, lambda t=task_name, r=rep+1, rt=repeat_task:
                                      self.execution_status_label.config(
                                          text=f"Ejecutando: {t} ({r}/{rt})"))

                        task = self.tasks[task_name]
                        events = task['events']
                        self._execute_events(events)

                        # Pausa entre repeticiones de la misma tarea
                        if rep < repeat_task - 1:
                            time.sleep(0.5)

                    # Pausa después de la tarea (excepto después de la última)
                    if i < len(processed_tasks) - 1:
                        time.sleep(pause_after)

                if not repeat_mode:
                    break

            self.root.after(0, lambda: self.execution_status_label.config(text="✅ Cola personalizada completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando cola personalizada: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="❌ Error en ejecución"))

    # ==================== MÉTODOS DEL SERVIDOR HTTP ====================

    def start_http_server(self):
        """Inicia el servidor HTTP"""
        success, message = self.http_server.start_server()

        if success:
            self.server_status = "running"
            self.server_status_label.config(text="🟢 Servidor ejecutándose")
            self.server_url_label.config(text=f"URL: http://localhost:{self.http_server.port}")
            self.start_server_btn.config(state="disabled")
            self.stop_server_btn.config(state="normal")
            messagebox.showinfo("Éxito", message)
        else:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor: {message}")

    def stop_http_server(self):
        """Detiene el servidor HTTP"""
        success, message = self.http_server.stop_server()

        self.server_status = "stopped"
        self.server_status_label.config(text="🔴 Servidor detenido")
        self.server_url_label.config(text="")
        self.start_server_btn.config(state="normal")
        self.stop_server_btn.config(state="disabled")

        if success:
            messagebox.showinfo("Información", message)
        else:
            messagebox.showwarning("Advertencia", message)

    def copy_api_examples(self):
        """Copia ejemplos de uso de la API al portapapeles"""
        if not self.http_server.is_running:
            messagebox.showwarning("Advertencia", "El servidor debe estar ejecutándose para copiar ejemplos")
            return

        port = self.http_server.port
        examples = f"""# Ejemplos de uso de la API - Puerto {port}

# Obtener estado del servidor
curl http://localhost:{port}/api/status

# Listar todas las tareas
curl http://localhost:{port}/api/tasks

# Ejecutar una tarea específica
curl -X POST http://localhost:{port}/api/execute/task \\
     -H "Content-Type: application/json" \\
     -d '{{"task_name": "nombre_de_tu_tarea"}}'

# Ejecutar cola de tareas
curl -X POST http://localhost:{port}/api/execute/queue \\
     -H "Content-Type: application/json" \\
     -d '{{"tasks": ["tarea1", "tarea2"], "pause_time": 1.5, "repeat": false}}'

# Python - Ejecutar tarea
import requests
response = requests.post('http://localhost:{port}/api/execute/task',
                        json={{'task_name': 'mi_tarea'}})
print(response.json())

# Python - Ejecutar cola
response = requests.post('http://localhost:{port}/api/execute/queue',
                        json={{
                            'tasks': ['tarea1', 'tarea2'],
                            'pause_time': 2.0,
                            'repeat': False
                        }})
print(response.json())"""

        # Copiar al portapapeles
        self.root.clipboard_clear()
        self.root.clipboard_append(examples)
        messagebox.showinfo("Éxito", "Ejemplos copiados al portapapeles")

    def test_api_connection(self):
        """Prueba la conexión con la API"""
        if not self.http_server.is_running:
            messagebox.showwarning("Advertencia", "El servidor debe estar ejecutándose para probar la API")
            return

        try:
            import requests

            # Probar endpoint de estado
            url = f"http://localhost:{self.http_server.port}/api/status"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                message = f"✅ API funcionando correctamente\n\n"
                message += f"Estado: {data['status']}\n"
                message += f"Puerto: {data['server_port']}\n"
                message += f"Tareas disponibles: {data['tasks_count']}\n"
                message += f"Endpoints: {len(data['available_endpoints'])}"

                messagebox.showinfo("Prueba de API", message)
            else:
                messagebox.showerror("Error", f"Error en la API: {response.status_code}")

        except ImportError:
            messagebox.showwarning("Advertencia",
                                 "La librería 'requests' no está instalada.\n"
                                 "Instálala con: pip install requests")
        except Exception as e:
            messagebox.showerror("Error", f"Error probando la API: {str(e)}")

    def start_area_capture(self):
        """Inicia la captura de área específica"""
        self.status_label.config(text="📸 Selecciona el área a capturar...")
        self.root.withdraw()  # Ocultar ventana principal temporalmente

        # Crear selector de área
        area_selector = AreaSelector(self.on_area_captured)

    def on_area_captured(self, filepath, screenshot_image):
        """Callback cuando se completa la captura de área"""
        self.root.deiconify()  # Mostrar ventana principal nuevamente
        self.last_screenshot = filepath

        # Actualizar UI
        self.status_label.config(text="✅ Screenshot capturado")
        self.screenshot_label.config(text=f"Último screenshot: {os.path.basename(filepath)}")

        # Mostrar mensaje de éxito
        messagebox.showinfo("Éxito", f"Screenshot guardado en:\n{filepath}")

    def play_recording(self):
        """Reproduce la grabación"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabación para reproducir")
            return

        self.is_playing = True
        self.play_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.status_label.config(text="▶️ Reproduciendo...")

        # Ejecutar reproducción en hilo separado
        threading.Thread(target=self._play_events, daemon=True).start()

    def _play_events(self):
        """Reproduce los eventos grabados"""
        try:
            last_time = 0
            for event in self.recorded_events:
                if not self.is_playing:
                    break

                # Esperar el tiempo correcto
                time_diff = event['time'] - last_time
                if time_diff > 0:
                    time.sleep(time_diff)
                last_time = event['time']

                # Ejecutar evento
                self._execute_event(event)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error durante reproducción: {str(e)}"))
        finally:
            self.is_playing = False
            self.root.after(0, self._finish_playback)

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

    def _finish_playback(self):
        """Finaliza la reproducción"""
        self.play_btn.config(state="normal")
        self.record_btn.config(state="normal")
        self.status_label.config(text="✅ Reproducción completada")

    def clear_recording(self):
        """Limpia la grabación actual"""
        if messagebox.askyesno("Confirmar", "¿Estás seguro de que quieres limpiar la grabación?"):
            self.recorded_events = []
            self.play_btn.config(state="disabled")
            self.status_label.config(text="Grabación limpiada")
            self.events_label.config(text="Eventos grabados: 0")

    def save_recording(self):
        """Guarda la grabación en un archivo"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabación para guardar")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Guardar grabación"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.recorded_events, f, indent=2)
                messagebox.showinfo("Éxito", f"Grabación guardada en: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def load_recording(self):
        """Carga una grabación desde un archivo"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Cargar grabación"
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    self.recorded_events = json.load(f)
                self.play_btn.config(state="normal")
                self.status_label.config(text="✅ Grabación cargada")
                self.events_label.config(text=f"Eventos grabados: {len(self.recorded_events)}")
                messagebox.showinfo("Éxito", f"Grabación cargada desde: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar: {str(e)}")

    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()

if __name__ == "__main__":
    app = MouseKeyboardRecorder()
    app.run()