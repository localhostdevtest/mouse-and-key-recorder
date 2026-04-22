import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import time
import threading
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
import os
import shutil
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

        # Canvas para dibujar la selecciÃ³n
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
            text="Haz clic y arrastra para seleccionar el Ã¡rea a capturar\nPresiona ESC para cancelar",
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

            # Asegurar que las coordenadas estÃ©n en el orden correcto
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)

            # Cerrar overlay antes de capturar
            self.overlay.destroy()

            # Capturar Ã¡rea seleccionada
            self.capture_area(x1, y1, x2, y2)

    def cancel_selection(self, event):
        self.overlay.destroy()
        self.parent_callback(None, None, None)

    def capture_area(self, x1, y1, x2, y2):
        try:
            # PequeÃ±a pausa para asegurar que el overlay se cierre completamente
            time.sleep(0.1)

            # Capturar el Ã¡rea seleccionada
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

            # Notificar al parent con el archivo, la imagen y las coordenadas
            self.parent_callback(filepath, screenshot, (x1, y1, x2, y2))

        except Exception as e:
            print(f"Error al capturar screenshot: {e}")
            self.parent_callback(None, None, None)

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
            """Ejecuta una tarea especÃ­fica"""
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
            """Ejecuta una cola personalizada con configuraciÃ³n avanzada"""
            try:
                data = request.get_json()
                if not data or 'queue' not in data:
                    return jsonify({'error': 'queue configuration is required'}), 400

                queue_config = data['queue']

                # Validar configuraciÃ³n de cola
                if 'tasks' not in queue_config:
                    return jsonify({'error': 'tasks array is required in queue'}), 400

                tasks = queue_config['tasks']
                global_pause = queue_config.get('global_pause_time', 1.0)
                repeat_mode = queue_config.get('repeat', False)
                repeat_count = queue_config.get('repeat_count', 0)  # 0 = infinito

                # Procesar tareas con configuraciÃ³n individual
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
                        # Tarea con configuraciÃ³n
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

        @self.app.route('/api/screenshots/web-action', methods=['POST'])
        def web_action_screenshot():
            """Desde la web, captura la region activa o abre el selector si no existe"""
            try:
                self.recorder.web_capture_or_select_region()
                return jsonify({
                    'success': True,
                    'message': 'Accion de captura iniciada'
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

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

        try:
            with open("desktop_http_port.txt", "w", encoding="utf-8") as f:
                f.write(str(self.port))
        except Exception as e:
            print(f"Error guardando puerto HTTP: {e}")

        return True, f"Server started on http://localhost:{self.port}"

    def stop_server(self):
        """Detiene el servidor HTTP"""
        if not self.is_running:
            return False, "Server is not running"

        # Flask no tiene una forma limpia de detener el servidor desde otro hilo
        # En un entorno de producciÃ³n usarÃ­as un servidor WSGI apropiado
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
        self.screenshot_regions = {}
        self.screenshot_region_file = "screenshot_regions.json"
        self.current_area_selector = None
        self.active_screenshot_region = None
        self.quick_prompts = []
        self.quick_prompts_file = "quick_prompts.json"
        self.recordings_dir = "recordings"

        # Configuracion de matriz
        self.matrix_entries = {}
        self.matrix_config_file = "matrix_config.json"

        # Sistema de tareas
        self.tasks = {}  # Diccionario de tareas guardadas
        self.current_task_name = ""

        # Servidor HTTP
        self.http_server = HTTPServer(self)
        self.server_status = "stopped"

        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None

        # Controladores para reproducciÃ³n
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.load_quick_prompts_from_file()
        self.setup_ui()

    def setup_ui(self):
        # Crear notebook para pestaÃ±as
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Pestaña 1: Botonera Principal
        self.main_panel_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_panel_frame, text="Botonera")
        self.setup_main_panel_tab()

        # Pestaña 2: Grabacion
        self.recording_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.recording_frame, text="Grabacion")
        self.setup_recording_tab()

        # Pestaña 3: Tareas
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="Tareas")
        self.setup_tasks_tab()

        # Pestaña 4: Prompts
        self.prompts_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.prompts_frame, text="Prompts")
        self.setup_prompts_tab()

        # Pestaña 5: Servidor HTTP
        self.server_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.server_frame, text="API Server")
        self.setup_server_tab()

        # Pestaña 6: Screenshots
        self.screenshot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.screenshot_frame, text="Screenshots")
        self.setup_screenshot_tab()

        # Pestaña 7: Matriz 3x3
        self.matrix_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.matrix_frame, text="Matriz (3x3)")
        self.setup_matrix_tab()

        # Cargar tareas guardadas al inicio
        self.load_tasks_from_file()
        self.load_screenshot_regions_from_file()
        self.load_matrix_config()
        self.refresh_prompt_tasks()
        self.refresh_screenshot_regions_list()
        self.refresh_main_panel()

    def setup_recording_tab(self):
        """Configura la pestaña de grabacion"""
        main_frame = ttk.Frame(self.recording_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Titulo
        title_label = ttk.Label(main_frame, text="Grabador de Mouse y Teclado",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Frame para botones principales
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        self.record_btn = ttk.Button(buttons_frame, text="Grabar",
                                   command=self.start_recording, width=15)
        self.record_btn.grid(row=0, column=0, padx=5, pady=5)

        self.stop_btn = ttk.Button(buttons_frame, text="Parar",
                                 command=self.stop_recording, width=15, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5)

        self.play_btn = ttk.Button(buttons_frame, text="Reproducir",
                                 command=self.play_recording, width=15, state="disabled")
        self.play_btn.grid(row=1, column=0, padx=5, pady=5)

        self.clear_btn = ttk.Button(buttons_frame, text="Limpiar",
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

        ttk.Label(task_frame, text="Descripcion (opcional):").pack(anchor=tk.W)
        self.task_desc_entry = ttk.Entry(task_frame, width=40)
        self.task_desc_entry.pack(fill=tk.X, pady=(5, 10))

        self.save_task_btn = ttk.Button(task_frame, text="Guardar como Tarea",
                                      command=self.save_as_task, state="disabled")
        self.save_task_btn.pack()

        # Separador
        separator2 = ttk.Separator(main_frame, orient='horizontal')
        separator2.pack(fill=tk.X, pady=20)

        # Botones de archivo (grabaciones individuales)
        file_frame = ttk.LabelFrame(main_frame, text="Archivos de Grabacion", padding="10")
        file_frame.pack(fill=tk.X, pady=10)

        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack()

        self.save_btn = ttk.Button(file_buttons_frame, text="Guardar Grabacion",
                                 command=self.save_recording, width=20)
        self.save_btn.grid(row=0, column=0, padx=5, pady=5)

        self.load_btn = ttk.Button(file_buttons_frame, text="Cargar Grabacion",
                                 command=self.load_recording, width=20)
        self.load_btn.grid(row=0, column=1, padx=5, pady=5)

        # Estado
        self.status_label = ttk.Label(main_frame, text="Listo para grabar",
                                    font=("Arial", 10))
        self.status_label.pack(pady=(20, 5))

        # Informacion de eventos
        self.events_label = ttk.Label(main_frame, text="Eventos grabados: 0",
                                    font=("Arial", 9))
        self.events_label.pack(pady=5)

    def setup_tasks_tab(self):
        """Configura la pestaña de tareas"""
        main_frame = ttk.Frame(self.tasks_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Titulo
        title_label = ttk.Label(main_frame, text="Gestion de Tareas",
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

        # Botones para gestion de tareas
        task_buttons_frame = ttk.Frame(left_frame)
        task_buttons_frame.pack(fill=tk.X, pady=(10, 0))

        self.delete_task_btn = ttk.Button(task_buttons_frame, text="Eliminar",
                                        command=self.delete_selected_tasks, width=12)
        self.delete_task_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.edit_task_btn = ttk.Button(task_buttons_frame, text="Editar",
                                      command=self.edit_selected_task, width=12)
        self.edit_task_btn.pack(side=tk.LEFT, padx=5)

        self.duplicate_task_btn = ttk.Button(task_buttons_frame, text="Duplicar",
                                           command=self.duplicate_selected_task, width=12)
        self.duplicate_task_btn.pack(side=tk.LEFT, padx=5)

        # Columna derecha - Ejecucion de tareas
        right_frame = ttk.LabelFrame(content_frame, text="Ejecucion de Tareas", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Lista de tareas seleccionadas para ejecutar
        ttk.Label(right_frame, text="Cola de Ejecucion:", font=("Arial", 12, "bold")).pack(anchor=tk.W)

        queue_frame = ttk.Frame(right_frame)
        queue_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.queue_listbox = tk.Listbox(queue_frame, height=10)
        scrollbar_queue = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_listbox.yview)
        self.queue_listbox.configure(yscrollcommand=scrollbar_queue.set)

        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_queue.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones para gestion de cola
        queue_buttons_frame = ttk.Frame(right_frame)
        queue_buttons_frame.pack(fill=tk.X, pady=(5, 10))

        self.add_to_queue_btn = ttk.Button(queue_buttons_frame, text="Agregar a Cola",
                                         command=self.add_to_queue, width=15)
        self.add_to_queue_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.remove_from_queue_btn = ttk.Button(queue_buttons_frame, text="Quitar de Cola",
                                              command=self.remove_from_queue, width=15)
        self.remove_from_queue_btn.pack(side=tk.LEFT, padx=5)

        self.clear_queue_btn = ttk.Button(queue_buttons_frame, text="Limpiar Cola",
                                        command=self.clear_queue, width=15)
        self.clear_queue_btn.pack(side=tk.LEFT, padx=5)

        # Botones de ejecucion
        execution_frame = ttk.LabelFrame(right_frame, text="Ejecucion", padding="10")
        execution_frame.pack(fill=tk.X, pady=(10, 0))

        self.run_queue_btn = ttk.Button(execution_frame, text="Ejecutar Cola",
                                      command=self.run_task_queue, width=20)
        self.run_queue_btn.pack(pady=5)

        self.run_selected_btn = ttk.Button(execution_frame, text="Ejecutar Seleccionada",
                                         command=self.run_selected_task, width=20)
        self.run_selected_btn.pack(pady=5)

        # Configuracion de ejecucion
        config_frame = ttk.LabelFrame(right_frame, text="Configuracion", padding="10")
        config_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(config_frame, text="Pausa entre tareas (segundos):").pack(anchor=tk.W)
        self.pause_var = tk.StringVar(value="1.0")
        self.pause_entry = ttk.Entry(config_frame, textvariable=self.pause_var, width=10)
        self.pause_entry.pack(anchor=tk.W, pady=(5, 10))

        self.repeat_var = tk.BooleanVar()
        self.repeat_checkbox = ttk.Checkbutton(config_frame, text="Repetir cola continuamente",
                                             variable=self.repeat_var)
        self.repeat_checkbox.pack(anchor=tk.W)

        # Estado de ejecuciÃ³n
        self.execution_status_label = ttk.Label(right_frame, text="Listo para ejecutar",
                                              font=("Arial", 10))
        self.execution_status_label.pack(pady=(10, 0))

    def setup_main_panel_tab(self):
        """Configura la botonera principal"""
        main_frame = ttk.Frame(self.main_panel_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="Botonera Principal",
                                font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))

        subtitle_label = ttk.Label(
            main_frame,
            text="Accesos rapidos a grabaciones, prompts y capturas desde un solo lugar."
        )
        subtitle_label.pack(pady=(0, 15))

        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.main_panel_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        main_panel_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.main_panel_canvas.yview)
        self.main_panel_inner = ttk.Frame(self.main_panel_canvas)

        self.main_panel_inner.bind(
            "<Configure>",
            lambda event: self.main_panel_canvas.configure(scrollregion=self.main_panel_canvas.bbox("all"))
        )

        self.main_panel_canvas.create_window((0, 0), window=self.main_panel_inner, anchor="nw")
        self.main_panel_canvas.configure(yscrollcommand=main_panel_scrollbar.set)
        self.main_panel_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        main_panel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Matriz Rapida en Botonera
        self.matrix_quick_section = ttk.LabelFrame(self.main_panel_inner, text="Ejecutar Matriz Rápida", padding="10")
        self.matrix_quick_section.pack(fill=tk.X, pady=(0, 12))
        
        matrix_input_frame = ttk.Frame(self.matrix_quick_section)
        matrix_input_frame.pack(fill=tk.X)
        
        ttk.Label(matrix_input_frame, text="Secuencia (ej: 1x2 3x3):").pack(side=tk.LEFT, padx=(0, 5))
        self.matrix_quick_var = tk.StringVar()
        ttk.Entry(matrix_input_frame, textvariable=self.matrix_quick_var, font=("Arial", 11)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(matrix_input_frame, text="▶ Ejecutar", command=lambda: self.execute_matrix_sequence(self.matrix_quick_var.get())).pack(side=tk.LEFT, padx=5)
        self.matrix_quick_status = ttk.Label(self.matrix_quick_section, text="", foreground="blue", font=("Arial", 9))
        self.matrix_quick_status.pack(pady=(5, 0))

        self.main_recordings_section = ttk.LabelFrame(self.main_panel_inner, text="Grabaciones", padding="10")
        self.main_recordings_section.pack(fill=tk.X, pady=(0, 12))

        self.main_prompts_section = ttk.LabelFrame(self.main_panel_inner, text="Prompts rapidos", padding="10")
        self.main_prompts_section.pack(fill=tk.X, pady=(0, 12))

        self.main_screenshots_section = ttk.LabelFrame(self.main_panel_inner, text="Capturas", padding="10")
        self.main_screenshots_section.pack(fill=tk.X, pady=(0, 12))

        self.refresh_main_panel()

    def setup_prompts_tab(self):
        """Configura la pestaÃ±a del teclado de prompts"""
        main_frame = ttk.Frame(self.prompts_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # TÃ­tulo
        title_label = ttk.Label(main_frame, text="Teclado de Prompts",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Creador rapido de prompts
        quick_frame = ttk.LabelFrame(main_frame, text="Creador de Prompts", padding="10")
        quick_frame.pack(fill=tk.X, pady=(0, 15))

        quick_top_row = ttk.Frame(quick_frame)
        quick_top_row.pack(fill=tk.X)

        title_col = ttk.Frame(quick_top_row)
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=(0, 10))
        ttk.Label(title_col, text="Titulo").pack(anchor=tk.W)
        self.quick_prompt_title_entry = ttk.Entry(title_col, width=32)
        self.quick_prompt_title_entry.pack(fill=tk.X)

        prompt_col = ttk.Frame(quick_top_row)
        prompt_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(prompt_col, text="Prompt").pack(anchor=tk.W)
        self.quick_prompt_text = tk.Text(prompt_col, height=4, wrap=tk.WORD)
        self.quick_prompt_text.pack(fill=tk.BOTH, expand=True)

        extra_row = ttk.Frame(quick_frame)
        extra_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(extra_row, text="Texto extra al copiar").pack(anchor=tk.W)
        self.quick_prompt_extra_entry = ttk.Entry(extra_row)
        self.quick_prompt_extra_entry.pack(fill=tk.X)

        quick_buttons = ttk.Frame(quick_frame)
        quick_buttons.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(quick_buttons, text="Guardar prompt", command=self.save_quick_prompt_from_form).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_buttons, text="Copiar prompt", command=self.copy_quick_prompt_from_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_buttons, text="Limpiar", command=self.clear_quick_prompt_form).pack(side=tk.LEFT, padx=5)

        # Prompts guardados
        saved_frame = ttk.LabelFrame(main_frame, text="Prompts Guardados", padding="10")
        saved_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 15))

        saved_header = ttk.Frame(saved_frame)
        saved_header.pack(fill=tk.X)
        ttk.Label(saved_header, text="Copiar solo el prompt o con texto extra").pack(side=tk.LEFT)
        self.quick_prompts_count_label = ttk.Label(saved_header, text="0")
        self.quick_prompts_count_label.pack(side=tk.RIGHT)

        self.quick_prompts_empty_label = ttk.Label(saved_frame, text="Todavia no guardaste prompts. Usa el creador de arriba para agregar el primero.")
        self.quick_prompts_empty_label.pack(anchor=tk.W, pady=(10, 0))

        saved_canvas_frame = ttk.Frame(saved_frame)
        saved_canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.quick_prompts_canvas = tk.Canvas(saved_canvas_frame, height=220, highlightthickness=0)
        quick_prompts_scrollbar = ttk.Scrollbar(saved_canvas_frame, orient=tk.VERTICAL, command=self.quick_prompts_canvas.yview)
        self.quick_prompts_cards_frame = ttk.Frame(self.quick_prompts_canvas)

        self.quick_prompts_cards_frame.bind(
            "<Configure>",
            lambda event: self.quick_prompts_canvas.configure(scrollregion=self.quick_prompts_canvas.bbox("all"))
        )

        self.quick_prompts_canvas.create_window((0, 0), window=self.quick_prompts_cards_frame, anchor="nw")
        self.quick_prompts_canvas.configure(yscrollcommand=quick_prompts_scrollbar.set)
        self.quick_prompts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        quick_prompts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.render_quick_prompts()

        # Frame principal con dos columnas
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Columna izquierda - Lista de tareas con prompts
        left_frame = ttk.LabelFrame(content_frame, text="Tareas con Prompts", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Listbox para tareas
        self.prompt_tasks_listbox = tk.Listbox(left_frame, height=12)
        scrollbar_prompt_tasks = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.prompt_tasks_listbox.yview)
        self.prompt_tasks_listbox.configure(yscrollcommand=scrollbar_prompt_tasks.set)
        self.prompt_tasks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_prompt_tasks.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind para selecciÃ³n de tarea
        self.prompt_tasks_listbox.bind('<<ListboxSelect>>', self.on_prompt_task_select)

        # Botones de gestiÃ³n de prompts
        prompt_buttons_frame = ttk.Frame(left_frame)
        prompt_buttons_frame.pack(fill=tk.X, pady=(10, 0))

        self.edit_prompt_btn = ttk.Button(prompt_buttons_frame, text="Editar Prompt",
                                        command=self.edit_task_prompt, width=15)
        self.edit_prompt_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.refresh_prompts_btn = ttk.Button(prompt_buttons_frame, text="Actualizar",
                                        command=self.refresh_prompt_tasks, width=15)
        self.refresh_prompts_btn.pack(side=tk.LEFT, padx=5)

        # Columna derecha - Generador de prompts
        right_frame = ttk.LabelFrame(content_frame, text="Generador de Prompts", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # InformaciÃ³n de la tarea seleccionada
        self.selected_task_label = ttk.Label(right_frame, text="Selecciona una tarea",
                                           font=("Arial", 12, "bold"))
        self.selected_task_label.pack(pady=(0, 10))

        # Template del prompt (solo lectura)
        ttk.Label(right_frame, text="Plantilla del Prompt:", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        template_frame = ttk.Frame(right_frame)
        template_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.prompt_template_text = tk.Text(template_frame, height=8, wrap=tk.WORD,
                                          font=("Arial", 9), state=tk.DISABLED)
        scrollbar_template = ttk.Scrollbar(template_frame, orient=tk.VERTICAL,
                                         command=self.prompt_template_text.yview)
        self.prompt_template_text.configure(yscrollcommand=scrollbar_template.set)
        self.prompt_template_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_template.pack(side=tk.RIGHT, fill=tk.Y)

        # Ã rea de contenido dinÃ¡mico
        dynamic_frame = ttk.LabelFrame(right_frame, text="Contenido DinÃ¡mico", padding="10")
        dynamic_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(dynamic_frame, text="Pega aquÃ­ el contenido variable (ej: HTML del botÃ³n):").pack(anchor=tk.W)

        self.dynamic_content_text = tk.Text(dynamic_frame, height=4, wrap=tk.WORD, font=("Consolas", 9))
        scrollbar_dynamic = ttk.Scrollbar(dynamic_frame, orient=tk.VERTICAL,
                                        command=self.dynamic_content_text.yview)
        self.dynamic_content_text.configure(yscrollcommand=scrollbar_dynamic.set)
        self.dynamic_content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_dynamic.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones de acciÃ³n
        action_buttons_frame = ttk.Frame(right_frame)
        action_buttons_frame.pack(fill=tk.X, pady=(15, 0))

        self.generate_prompt_btn = ttk.Button(action_buttons_frame, text="Generar Prompt Final",
                                        command=self.generate_final_prompt, width=20)
        self.generate_prompt_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.copy_prompt_btn = ttk.Button(action_buttons_frame, text="Copiar al Portapapeles",
                                      command=self.copy_final_prompt, width=20)
        self.copy_prompt_btn.pack(side=tk.LEFT, padx=5)

        # Ã rea del prompt final
        final_frame = ttk.LabelFrame(right_frame, text="Prompt Final Generado", padding="10")
        final_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        self.final_prompt_text = tk.Text(final_frame, height=6, wrap=tk.WORD,
                                       font=("Arial", 9), state=tk.DISABLED)
        scrollbar_final = ttk.Scrollbar(final_frame, orient=tk.VERTICAL,
                                      command=self.final_prompt_text.yview)
        self.final_prompt_text.configure(yscrollcommand=scrollbar_final.set)
        self.final_prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_final.pack(side=tk.RIGHT, fill=tk.Y)

        # Cargar tareas al inicio
        self.refresh_prompt_tasks()

    def setup_server_tab(self):
        """Configura la pestaÃ±a del servidor HTTP"""
        main_frame = ttk.Frame(self.server_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # TÃ­tulo
        title_label = ttk.Label(main_frame, text="Servidor API HTTP",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Estado del servidor
        status_frame = ttk.LabelFrame(main_frame, text="Estado del Servidor", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 20))

        self.server_status_label = ttk.Label(status_frame, text="Servidor detenido",
                                           font=("Arial", 12))
        self.server_status_label.pack(pady=5)

        self.server_url_label = ttk.Label(status_frame, text="",
                                        font=("Arial", 10), foreground="blue")
        self.server_url_label.pack(pady=5)

        # Controles del servidor
        controls_frame = ttk.Frame(status_frame)
        controls_frame.pack(pady=10)

        self.start_server_btn = ttk.Button(controls_frame, text="Iniciar Servidor",
                                         command=self.start_http_server, width=20)
        self.start_server_btn.pack(side=tk.LEFT, padx=5)

        self.stop_server_btn = ttk.Button(controls_frame, text="Detener Servidor",
                                        command=self.stop_http_server, width=20, state="disabled")
        self.stop_server_btn.pack(side=tk.LEFT, padx=5)

        # Documentacion de la API
        api_frame = ttk.LabelFrame(main_frame, text="Documentacion de la API", padding="15")
        api_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Crear un widget de texto con scrollbar para la documentacion
        doc_frame = ttk.Frame(api_frame)
        doc_frame.pack(fill=tk.BOTH, expand=True)

        self.api_doc_text = tk.Text(doc_frame, wrap=tk.WORD, height=20, font=("Consolas", 9))
        scrollbar_doc = ttk.Scrollbar(doc_frame, orient=tk.VERTICAL, command=self.api_doc_text.yview)
        self.api_doc_text.configure(yscrollcommand=scrollbar_doc.set)

        self.api_doc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_doc.pack(side=tk.RIGHT, fill=tk.Y)

        # Insertar documentacion
        self.insert_api_documentation()

        # Botones de utilidad
        utils_frame = ttk.Frame(main_frame)
        utils_frame.pack(fill=tk.X, pady=10)

        self.copy_examples_btn = ttk.Button(utils_frame, text="Copiar Ejemplos",
                                          command=self.copy_api_examples, width=20)
        self.copy_examples_btn.pack(side=tk.LEFT, padx=5)

        self.test_api_btn = ttk.Button(utils_frame, text="Probar API",
                                     command=self.test_api_connection, width=20)
        self.test_api_btn.pack(side=tk.LEFT, padx=5)

    def insert_api_documentation(self):
        """Inserta la documentaciÃ³n de la API en el widget de texto"""
        doc_text = """
API HTTP

El servidor HTTP permite ejecutar tareas y colas mediante peticiones POST.
Base URL: http://localhost:PUERTO

ENDPOINTS DISPONIBLES:
1. GET /api/status
2. GET /api/tasks
3. POST /api/execute/task
4. POST /api/execute/queue
5. POST /api/execute/custom-queue

EJEMPLOS DE USO:
curl http://localhost:8080/api/status
curl http://localhost:8080/api/tasks
curl -X POST http://localhost:8080/api/execute/task -H "Content-Type: application/json" -d '{"task_name": "mi_tarea"}'
"""
        self.api_doc_text.insert(tk.END, doc_text)
        self.api_doc_text.config(state=tk.DISABLED)  # Solo lectura

    def setup_screenshot_tab(self):
        """Configura la pestaña de captura de pantalla"""
        main_frame = ttk.Frame(self.screenshot_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Titulo
        title_label = ttk.Label(main_frame, text="Captura de Pantalla",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 15))

        self.screenshot_btn = ttk.Button(
            controls_frame,
            text="Nueva Captura Exacta",
            command=self.start_area_capture,
            width=24
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.capture_region_btn = ttk.Button(
            controls_frame,
            text="Capturar Seleccionada",
            command=self.capture_selected_screenshot_region,
            width=24
        )
        self.capture_region_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.delete_region_btn = ttk.Button(
            controls_frame,
            text="Eliminar Region",
            command=self.delete_selected_screenshot_region,
            width=20
        )
        self.delete_region_btn.pack(side=tk.LEFT)

        self.clear_screenshots_btn = ttk.Button(
            controls_frame,
            text="Vaciar Capturas",
            command=self.clear_screenshots_folder,
            width=20
        )
        self.clear_screenshots_btn.pack(side=tk.LEFT, padx=(10, 0))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(list_frame, text="Regiones guardadas:", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        self.screenshot_regions_listbox = tk.Listbox(list_frame, height=8)
        self.screenshot_regions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(5, 0))

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.screenshot_regions_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(5, 0))
        self.screenshot_regions_listbox.config(yscrollcommand=scrollbar.set)

        self.screenshot_regions_listbox.bind('<Double-Button-1>', lambda event: self.capture_selected_screenshot_region())

        self.screenshot_label = ttk.Label(main_frame, text="",
                                        font=("Arial", 10), foreground="blue")
        self.screenshot_label.pack(pady=(15, 0))

        self.refresh_screenshot_regions_list()

    def setup_matrix_tab(self):
        """Configura la pestaña de la matriz 3x3"""
        main_frame = ttk.Frame(self.matrix_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="Matriz de Coordenadas (3x3)", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))

        inst_label = ttk.Label(main_frame, text="1. Usa 'Capturar (3s)' para guardar las coordenadas de cada elemento.\n2. Pega una secuencia como '1x2 1x3 3x3' y haz click en Ejecutar.", justify=tk.CENTER)
        inst_label.pack(pady=5)

        # Matriz Frame
        matrix_frame = ttk.LabelFrame(main_frame, text="Elementos de la Matriz", padding="10")
        matrix_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        matrix_frame.columnconfigure(0, weight=1)
        matrix_frame.columnconfigure(1, weight=1)
        matrix_frame.columnconfigure(2, weight=1)

        for r in range(1, 4):
            for c in range(1, 4):
                key = f"{r}x{c}"
                cell_frame = ttk.Frame(matrix_frame, borderwidth=1, relief="groove", padding=5)
                cell_frame.grid(row=r-1, column=c-1, padx=5, pady=5, sticky="nsew")

                ttk.Label(cell_frame, text=f"Item: {key}", font=("Arial", 10, "bold")).pack()
                entry_var = tk.StringVar()
                entry = ttk.Entry(cell_frame, textvariable=entry_var, width=12, justify="center")
                entry.pack(pady=5)

                btn = ttk.Button(cell_frame, text="Capturar (3s)", command=lambda k=key, var=entry_var: self.capture_matrix_coords(k, var))
                btn.pack()
                self.matrix_entries[key] = entry_var

        # Ejecución Frame
        exec_frame = ttk.LabelFrame(main_frame, text="Ejecutar Secuencia", padding="10")
        exec_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(exec_frame, text="Secuencia (ej: 1x2 2x3 3x3):").pack(anchor=tk.W)
        self.matrix_sequence_var = tk.StringVar()
        self.matrix_sequence_entry = ttk.Entry(exec_frame, textvariable=self.matrix_sequence_var, font=("Arial", 11))
        self.matrix_sequence_entry.pack(fill=tk.X, pady=5)

        btn_frame = ttk.Frame(exec_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="💾 Guardar Coordenadas", command=self.save_matrix_config).pack(side=tk.LEFT, padx=5)
        self.matrix_ejecutar_btn = ttk.Button(btn_frame, text="▶ Ejecutar Secuencia", command=self.execute_matrix_sequence)
        self.matrix_ejecutar_btn.pack(side=tk.RIGHT, padx=5)

        self.matrix_status_var = tk.StringVar(value="ESTADO: Listo")
        ttk.Label(main_frame, textvariable=self.matrix_status_var, font=("Arial", 10, "bold"), foreground="blue").pack(pady=5)

    def capture_matrix_coords(self, key, var):
        def task():
            for i in range(3, 0, -1):
                self.matrix_status_var.set(f"ESTADO: Capturando {key} en {i} segs... (Mueve el mouse)")
                self.root.update()
                time.sleep(1)
            
            x, y = self.mouse_controller.position
            var.set(f"{int(x)}, {int(y)}")
            self.matrix_status_var.set(f"ESTADO: Guardado {key} -> ({int(x)}, {int(y)})")
            self.root.update()
            
        threading.Thread(target=task, daemon=True).start()

    def save_matrix_config(self):
        data = {k: v.get() for k, v in self.matrix_entries.items()}
        try:
            with open(self.matrix_config_file, "w") as f:
                json.dump(data, f)
            self.matrix_status_var.set(f"ESTADO: Config guardada en {self.matrix_config_file} exitosamente!")
        except Exception as e:
            self.matrix_status_var.set(f"ESTADO: Error al guardar - {str(e)}")

    def load_matrix_config(self):
        if os.path.exists(self.matrix_config_file):
            try:
                with open(self.matrix_config_file, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in self.matrix_entries:
                            self.matrix_entries[k].set(v)
            except Exception as e:
                print(f"Error cargando config matriz: {e}")

    def execute_matrix_sequence(self, sequence=None):
        seq = sequence if sequence is not None else self.matrix_sequence_var.get()
        seq = seq.strip()
        
        if not seq:
            self.matrix_status_var.set("ESTADO: Ingresa una secuencia.")
            if hasattr(self, 'matrix_quick_status'): self.matrix_quick_status.config(text="ESTADO: Ingresa una secuencia.")
            return
            
        items = seq.split()
        if hasattr(self, 'matrix_ejecutar_btn'): self.matrix_ejecutar_btn.state(['disabled'])
        
        def task():
            for item in items:
                if item in self.tasks:
                    status_text = f"ESTADO: Ejecutando Tarea '{item}'..."
                    self.matrix_status_var.set(status_text)
                    if hasattr(self, 'matrix_quick_status'): self.matrix_quick_status.config(text=status_text)
                    self.root.update()
                    self._execute_single_task(item)
                    time.sleep(0.5)
                elif item in self.matrix_entries:
                    val = self.matrix_entries[item].get()
                    if val and "," in val:
                        try:
                            x, y = map(int, val.replace(" ", "").split(","))
                            status_text = f"ESTADO: Clickeando en {item}..."
                            self.matrix_status_var.set(status_text)
                            if hasattr(self, 'matrix_quick_status'): self.matrix_quick_status.config(text=status_text)
                            self.root.update()
                            self.mouse_controller.position = (x, y)
                            time.sleep(0.2)
                            self.mouse_controller.click(Button.left)
                            time.sleep(0.5)
                        except ValueError:
                            pass
            
            final_status = "ESTADO: Completado."
            self.matrix_status_var.set(final_status)
            if hasattr(self, 'matrix_quick_status'): self.matrix_quick_status.config(text=final_status)
            if hasattr(self, 'matrix_ejecutar_btn'): self.root.after(0, lambda: self.matrix_ejecutar_btn.state(['!disabled']))
            
        threading.Thread(target=task, daemon=True).start()

    def start_recording(self):
        """Inicia la grabacion de eventos"""
        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()

        # Actualizar UI
        self.record_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.play_btn.config(state="disabled")
        self.status_label.config(text="Grabando... (Presiona PARAR para terminar)")
        self.events_label.config(text="Eventos grabados: 0")

        # Iniciar listeners
        self.start_listeners()

    def stop_recording(self):
        """Detiene la grabacion de eventos"""
        self.is_recording = False

        # Detener listeners
        self.stop_listeners()

        # Actualizar UI
        self.record_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.recorded_events:
            self.play_btn.config(state="normal")
            self.save_task_btn.config(state="normal")
            self.status_label.config(text="Grabacion completada")

            # Mostrar automÃ¡ticamente el diÃ¡logo para guardar la grabaciÃ³n
            self.show_save_dialog()
        else:
            self.status_label.config(text="No se grabaron eventos")

        self.events_label.config(text=f"Eventos grabados: {len(self.recorded_events)}")
        self.refresh_main_panel()

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

    # ==================== MÃ‰TODOS DE GESTIÃ“N DE TAREAS ====================

    def show_save_dialog(self):
        """Muestra el dialogo para guardar la grabacion automaticamente"""
        if not self.recorded_events:
            return

        # Crear ventana de diÃ¡logo
        save_dialog = tk.Toplevel(self.root)
        save_dialog.title("Guardar Grabacion")
        save_dialog.geometry("450x300")
        save_dialog.transient(self.root)
        save_dialog.grab_set()
        save_dialog.resizable(False, False)

        # Centrar la ventana
        save_dialog.update_idletasks()
        x = (save_dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (save_dialog.winfo_screenheight() // 2) - (300 // 2)
        save_dialog.geometry(f"450x300+{x}+{y}")

        # Frame principal
        main_frame = ttk.Frame(save_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # TÃ­tulo
        title_label = ttk.Label(main_frame, text="Grabacion completada",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))

        # Informacion de la grabacion
        info_label = ttk.Label(main_frame,
                              text=f"Se grabaron {len(self.recorded_events)} eventos",
                              font=("Arial", 11))
        info_label.pack(pady=(0, 20))

        # Campo para el nombre
        ttk.Label(main_frame, text="Nombre de la grabacion:",
                 font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var, width=40, font=("Arial", 10))
        name_entry.pack(fill=tk.X, pady=(0, 15))
        name_entry.focus_set()

        # Campo para la descripcion (opcional)
        ttk.Label(main_frame, text="Descripcion (opcional):",
                 font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        desc_var = tk.StringVar()
        desc_entry = ttk.Entry(main_frame, textvariable=desc_var, width=40, font=("Arial", 10))
        desc_entry.pack(fill=tk.X, pady=(0, 20))

        # Frame para botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=(10, 0))

        def save_recording():
            task_name = name_var.get().strip()
            if not task_name:
                messagebox.showwarning("Advertencia", "Por favor ingresa un nombre para la grabacion")
                name_entry.focus_set()
                return

            if task_name in self.tasks:
                if not messagebox.askyesno("Confirmar",
                                         f"La grabacion '{task_name}' ya existe. Deseas sobrescribirla?"):
                    name_entry.focus_set()
                    return

            task_description = desc_var.get().strip()

            # Crear objeto tarea
            task = {
                'name': task_name,
                'description': task_description,
                'events': self.recorded_events.copy(),
                'created_at': datetime.now().isoformat(),
                'event_count': len(self.recorded_events),
                'prompt_template': ''
            }

            # Guardar tarea
            self.tasks[task_name] = task
            self.save_tasks_to_file()
            self.refresh_tasks_list()

            # Cerrar dialogo
            save_dialog.destroy()

            # Mostrar mensaje de exito
            messagebox.showinfo("Exito", f"Grabacion '{task_name}' guardada correctamente")

        def skip_save():
            save_dialog.destroy()

        # Botones
        save_btn = ttk.Button(buttons_frame, text="Guardar",
                             command=save_recording, width=15)
        save_btn.pack(side=tk.LEFT, padx=(0, 10))

        skip_btn = ttk.Button(buttons_frame, text="Omitir",
                             command=skip_save, width=15)
        skip_btn.pack(side=tk.LEFT)

        # Permitir guardar con Enter
        def on_enter(event):
            save_recording()

        name_entry.bind('<Return>', on_enter)
        desc_entry.bind('<Return>', on_enter)

        # Generar nombre sugerido basado en timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"grabacion_{timestamp}"
        name_var.set(suggested_name)
        name_entry.select_range(0, tk.END)

    def save_as_task(self):
        """Guarda la grabacion actual como una tarea"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabacion para guardar como tarea")
            return

        task_name = self.task_name_entry.get().strip()
        if not task_name:
            messagebox.showwarning("Advertencia", "Por favor ingresa un nombre para la tarea")
            return

        if task_name in self.tasks:
            if not messagebox.askyesno("Confirmar", f"La tarea '{task_name}' ya existe. Deseas sobrescribirla?"):
                return

        task_description = self.task_desc_entry.get().strip()

        # Crear objeto tarea
        task = {
            'name': task_name,
            'description': task_description,
            'events': self.recorded_events.copy(),
            'created_at': datetime.now().isoformat(),
            'event_count': len(self.recorded_events),
            'prompt_template': ''
        }

        # Guardar tarea
        self.tasks[task_name] = task
        self.save_tasks_to_file()
        self.refresh_tasks_list()

        # Limpiar campos
        self.task_name_entry.delete(0, tk.END)
        self.task_desc_entry.delete(0, tk.END)

        messagebox.showinfo("Exito", f"Tarea '{task_name}' guardada correctamente")

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

    def load_screenshot_regions_from_file(self):
        """Carga las regiones de captura desde archivo"""
        regions_file = "screenshot_regions.json"
        if os.path.exists(regions_file):
            try:
                with open(regions_file, 'r', encoding='utf-8') as f:
                    self.screenshot_regions = json.load(f)
            except Exception as e:
                print(f"Error cargando regiones de captura: {e}")
                self.screenshot_regions = {}
        else:
            self.screenshot_regions = {}

    def save_screenshot_regions_to_file(self):
        """Guarda las regiones de captura en archivo"""
        regions_file = "screenshot_regions.json"
        try:
            with open(regions_file, 'w', encoding='utf-8') as f:
                json.dump(self.screenshot_regions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando regiones de captura: {e}")
            if hasattr(self, "status_label"):
                self.status_label.config(text=f"Error guardando regiones de captura: {str(e)}")

    def load_quick_prompts_from_file(self):
        """Carga los prompts rapidos desde archivo"""
        if os.path.exists(self.quick_prompts_file):
            try:
                with open(self.quick_prompts_file, 'r', encoding='utf-8') as f:
                    self.quick_prompts = json.load(f)
                if not isinstance(self.quick_prompts, list):
                    self.quick_prompts = []
            except Exception as e:
                print(f"Error cargando prompts rapidos: {e}")
                self.quick_prompts = []
        else:
            self.quick_prompts = []

    def save_quick_prompts_to_file(self):
        """Guarda los prompts rapidos en archivo"""
        try:
            with open(self.quick_prompts_file, 'w', encoding='utf-8') as f:
                json.dump(self.quick_prompts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando prompts rapidos: {e}")
            if hasattr(self, "status_label"):
                self.status_label.config(text=f"Error guardando prompts: {str(e)}")
    def delete_selected_tasks(self):
        """Elimina las tareas seleccionadas"""
        selected_indices = self.tasks_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos una tarea para eliminar")
            return

        task_names = list(self.tasks.keys())
        selected_tasks = [task_names[i] for i in selected_indices]

        if messagebox.askyesno("Confirmar", f"Estas seguro de eliminar {len(selected_tasks)} tarea(s)?"):
            for task_name in selected_tasks:
                del self.tasks[task_name]

            self.save_tasks_to_file()
            self.refresh_tasks_list()
            messagebox.showinfo("Exito", f"{len(selected_tasks)} tarea(s) eliminada(s)")

    def edit_selected_task(self):
        """Edita la tarea seleccionada"""
        selected_indices = self.tasks_listbox.curselection()
        if len(selected_indices) != 1:
            messagebox.showwarning("Advertencia", "Selecciona exactamente una tarea para editar")
            return

        task_names = list(self.tasks.keys())
        task_name = task_names[selected_indices[0]]
        task = self.tasks[task_name]

        # Crear ventana de ediciÃ³n
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Editar Tarea: {task_name}")
        edit_window.geometry("400x300")
        edit_window.transient(self.root)
        edit_window.grab_set()

        # Campos de ediciÃ³n
        ttk.Label(edit_window, text="Nombre:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=20, pady=(20, 5))
        name_var = tk.StringVar(value=task_name)
        name_entry = ttk.Entry(edit_window, textvariable=name_var, width=50)
        name_entry.pack(padx=20, pady=(0, 10))

        ttk.Label(edit_window, text="Descripcion:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=20, pady=(10, 5))
        desc_var = tk.StringVar(value=task.get('description', ''))
        desc_entry = ttk.Entry(edit_window, textvariable=desc_var, width=50)
        desc_entry.pack(padx=20, pady=(0, 10))

        # InformaciÃ³n de la tarea
        info_frame = ttk.LabelFrame(edit_window, text="InformaciÃ³n", padding="10")
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
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacio")
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
            messagebox.showinfo("Exito", "Tarea actualizada correctamente")

        ttk.Button(buttons_frame, text="Guardar", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)

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

        messagebox.showinfo("Exito", f"Tarea duplicada como '{new_name}'")

    def add_to_queue(self):
        """Agrega tareas seleccionadas a la cola de ejecuciÃ³n"""
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
        """Quita tareas seleccionadas de la cola de ejecuciÃ³n"""
        selected_indices = self.queue_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos una tarea para quitar de la cola")
            return

        # Eliminar en orden inverso para mantener Ã­ndices vÃ¡lidos
        for index in reversed(selected_indices):
            self.queue_listbox.delete(index)

    def clear_queue(self):
        """Limpia toda la cola de ejecuciÃ³n"""
        if self.queue_listbox.size() > 0:
            if messagebox.askyesno("Confirmar", "Estas seguro de limpiar toda la cola?"):
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
            messagebox.showwarning("Advertencia", "La cola esta vacia")
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

            self.root.after(0, lambda: self.execution_status_label.config(text="Tarea completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando tarea: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="Error en ejecucion"))

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

                    # Pausa entre tareas (excepto despues de la ultima)
                    if i < len(queue_tasks) - 1:
                        time.sleep(pause_time)

                if not repeat_mode:
                    break

                cycle_count += 1
                # Pausa antes del siguiente ciclo
                time.sleep(pause_time)

            self.root.after(0, lambda: self.execution_status_label.config(text="Cola completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando cola: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="Error en ejecucion"))

    def get_quick_prompt_form_values(self):
        """Obtiene los valores del creador rapido"""
        return {
            'title': self.quick_prompt_title_entry.get().strip(),
            'prompt': self.quick_prompt_text.get(1.0, tk.END).strip(),
            'extra': self.quick_prompt_extra_entry.get().strip()
        }

    def compose_quick_prompt_text(self, prompt_text, extra_text):
        """Concatena el prompt con texto extra si existe"""
        if extra_text:
            return f"{prompt_text}\n\n{extra_text}"
        return prompt_text

    def get_recording_files(self):
        """Devuelve la lista de grabaciones guardadas en disco"""
        files = []
        if not os.path.exists(self.recordings_dir):
            return files

        for entry in sorted(os.listdir(self.recordings_dir), reverse=True):
            if not entry.lower().endswith('.json'):
                continue
            path = os.path.join(self.recordings_dir, entry)
            if os.path.isfile(path):
                files.append({
                    'name': entry,
                    'path': path
                })
        return files

    def play_recording_file(self, filepath):
        """Carga y reproduce una grabacion desde archivo"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.recorded_events = json.load(f)
            self.events_label.config(text=f"Eventos grabados: {len(self.recorded_events)}")
            self.play_recording()
            self.status_label.config(text=f"Reproduciendo: {os.path.basename(filepath)}")
        except Exception as e:
            self.status_label.config(text=f"Error al reproducir archivo: {str(e)}")

    def render_quick_prompts(self):
        """Renderiza los prompts rapidos guardados"""
        if not hasattr(self, "quick_prompts_cards_frame"):
            return

        for widget in self.quick_prompts_cards_frame.winfo_children():
            widget.destroy()

        self.quick_prompts_count_label.config(text=str(len(self.quick_prompts)))

        if not self.quick_prompts:
            self.quick_prompts_empty_label.pack(anchor=tk.W, pady=(10, 0))
            return

        self.quick_prompts_empty_label.pack_forget()

        for prompt_item in self.quick_prompts:
            row = ttk.Frame(self.quick_prompts_cards_frame, relief=tk.RIDGE, padding=8)
            row.pack(fill=tk.X, pady=4)

            ttk.Label(row, text=prompt_item.get('title', ''), width=28).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))

            extra_entry = ttk.Entry(row)
            extra_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 8))
            extra_entry.insert(0, "")

            prompt_id = prompt_item.get('id', '')
            ttk.Button(
                row,
                text="Copiar",
                command=lambda pid=prompt_id, extra_widget=extra_entry: self.copy_saved_quick_prompt(pid, extra_widget),
                width=12
            ).grid(row=0, column=2, sticky=tk.E)

            row.columnconfigure(1, weight=1)

    def save_quick_prompt_from_form(self):
        """Guarda un prompt rapido nuevo"""
        values = self.get_quick_prompt_form_values()

        if not values['title']:
            self.status_label.config(text="Escribe un titulo para el prompt")
            return

        if not values['prompt']:
            self.status_label.config(text="Escribe el prompt antes de guardarlo")
            return

        self.quick_prompts.insert(0, {
            'id': f"{int(time.time() * 1000)}-{os.urandom(3).hex()}",
            'title': values['title'],
            'prompt': values['prompt'],
            'extra': values['extra']
        })
        self.save_quick_prompts_to_file()
        self.render_quick_prompts()
        self.refresh_main_panel()
        self.clear_quick_prompt_form()
        self.status_label.config(text="Prompt guardado correctamente")

    def copy_quick_prompt_from_form(self):
        """Copia el prompt del formulario rapido"""
        values = self.get_quick_prompt_form_values()

        if not values['prompt']:
            self.status_label.config(text="Escribe un prompt para copiar")
            return

        text_to_copy = self.compose_quick_prompt_text(values['prompt'], values['extra'])
        self.root.clipboard_clear()
        self.root.clipboard_append(text_to_copy)
        self.quick_prompt_extra_entry.delete(0, tk.END)
        self.status_label.config(text="Prompt copiado al portapapeles")

    def copy_saved_quick_prompt(self, prompt_id, extra_widget=None):
        """Copia un prompt guardado con texto extra opcional"""
        prompt_item = next((item for item in self.quick_prompts if item.get('id') == prompt_id), None)
        if not prompt_item:
            self.status_label.config(text="No se encontro el prompt")
            return

        runtime_extra = ""
        if extra_widget is not None:
            runtime_extra = extra_widget.get().strip()

        combined_extra = "\n\n".join([text for text in [prompt_item.get('extra', '').strip(), runtime_extra] if text])
        text_to_copy = self.compose_quick_prompt_text(prompt_item.get('prompt', ''), combined_extra)

        self.root.clipboard_clear()
        self.root.clipboard_append(text_to_copy)
        if extra_widget is not None:
            extra_widget.delete(0, tk.END)
        self.status_label.config(text=f'Prompt "{prompt_item.get("title", "")}" copiado')

    def delete_saved_quick_prompt(self, prompt_id):
        """Elimina un prompt guardado"""
        prompt_item = next((item for item in self.quick_prompts if item.get('id') == prompt_id), None)
        if not prompt_item:
            return

        self.quick_prompts = [item for item in self.quick_prompts if item.get('id') != prompt_id]
        self.save_quick_prompts_to_file()
        self.render_quick_prompts()
        self.refresh_main_panel()
        self.status_label.config(text=f'Prompt "{prompt_item.get("title", "")}" eliminado')

    def clear_quick_prompt_form(self):
        """Limpia el formulario rapido"""
        self.quick_prompt_title_entry.delete(0, tk.END)
        self.quick_prompt_text.delete(1.0, tk.END)
        self.quick_prompt_extra_entry.delete(0, tk.END)

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
        """Ejecuta una cola personalizada con configuraciÃ³n avanzada"""
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

                    # Pausa despuÃ©s de la tarea (excepto despuÃ©s de la Ãºltima)
                    if i < len(processed_tasks) - 1:
                        time.sleep(pause_after)

                if not repeat_mode:
                    break

            self.root.after(0, lambda: self.execution_status_label.config(text="Cola personalizada completada"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error ejecutando cola personalizada: {str(e)}"))
            self.root.after(0, lambda: self.execution_status_label.config(text="Error en ejecucion"))

    # ==================== MÃ‰TODOS DEL TECLADO DE PROMPTS ====================

    def refresh_main_panel(self):
        """Renderiza la botonera principal con accesos rapidos"""
        if not hasattr(self, "main_recordings_section"):
            return

        for section in [self.main_recordings_section, self.main_prompts_section, self.main_screenshots_section]:
            for widget in section.winfo_children():
                widget.destroy()

        recordings_header = ttk.Frame(self.main_recordings_section)
        recordings_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(recordings_header, text="Tareas y Grabaciones").pack(side=tk.LEFT)
        ttk.Button(recordings_header, text="Refrescar", command=self.refresh_main_panel, width=12).pack(side=tk.RIGHT)

        recordings_table = ttk.Frame(self.main_recordings_section)
        recordings_table.pack(fill=tk.X)

        ttk.Label(recordings_table, text="Nombre", width=44).grid(row=0, column=0, sticky=tk.W, padx=4)
        ttk.Label(recordings_table, text="Accion", width=12).grid(row=0, column=1, sticky=tk.W, padx=4)

        if self.recorded_events:
            current_row = ttk.Frame(recordings_table, relief=tk.RIDGE, padding=6)
            current_row.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=3)

            ttk.Label(current_row, text=f"Grabacion actual ({len(self.recorded_events)} eventos)").grid(row=0, column=0, sticky=tk.W, padx=4)
            ttk.Button(
                current_row,
                text="Reproducir",
                command=self.play_recording,
                width=12
            ).grid(row=0, column=1, sticky=tk.E, padx=4)

        recording_files = self.get_recording_files()
        
        combined_list = []
        for name, task_info in self.tasks.items():
            combined_list.append({"name": f"[Tarea] {name}", "is_task": True, "target": name})
        for f in recording_files:
            combined_list.append({"name": f"[Archivo] {f['name']}", "is_task": False, "target": f['path']})

        if not combined_list:
            ttk.Label(recordings_table, text="No hay tareas ni grabaciones guardadas.").grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=4, pady=(6, 0))
        else:
            start_row = 2 if self.recorded_events else 1
            for idx, item in enumerate(combined_list, start=start_row):
                row = ttk.Frame(recordings_table, relief=tk.RIDGE, padding=6)
                row.grid(row=idx, column=0, columnspan=2, sticky=tk.EW, pady=3)

                ttk.Label(row, text=item['name']).grid(row=0, column=0, sticky=tk.W, padx=4)
                
                if item['is_task']:
                    cmd = lambda t=item['target']: threading.Thread(target=self._execute_single_task, args=(t,), daemon=True).start()
                else:
                    cmd = lambda p=item['target']: self.play_recording_file(p)

                ttk.Button(
                    row,
                    text="Reproducir",
                    command=cmd,
                    width=12
                ).grid(row=0, column=1, sticky=tk.E, padx=4)
                row.columnconfigure(0, weight=1)

        if not self.quick_prompts:
            ttk.Label(self.main_prompts_section, text="Todavia no hay prompts guardados.").pack(anchor=tk.W)
        else:
            prompt_table = ttk.Frame(self.main_prompts_section)
            prompt_table.pack(fill=tk.X)

            ttk.Label(prompt_table, text="Titulo", width=28).grid(row=0, column=0, sticky=tk.W, padx=4)
            ttk.Label(prompt_table, text="Extra", width=34).grid(row=0, column=1, sticky=tk.W, padx=4)
            ttk.Label(prompt_table, text="Accion", width=12).grid(row=0, column=2, sticky=tk.W, padx=4)

            for idx, prompt_item in enumerate(self.quick_prompts, start=1):
                row = ttk.Frame(prompt_table, relief=tk.RIDGE, padding=6)
                row.grid(row=idx, column=0, columnspan=3, sticky=tk.EW, pady=3)

                ttk.Label(row, text=prompt_item.get('title', ''), width=28).grid(row=0, column=0, sticky=tk.W, padx=4)
                extra_entry = ttk.Entry(row)
                extra_entry.grid(row=0, column=1, sticky=tk.EW, padx=4)

                prompt_id = prompt_item.get('id', '')
                ttk.Button(
                    row,
                    text="Copiar",
                    command=lambda pid=prompt_id, extra_widget=extra_entry: self.copy_saved_quick_prompt(pid, extra_widget),
                    width=12
                ).grid(row=0, column=2, sticky=tk.E, padx=4)
                row.columnconfigure(1, weight=1)

        capture_header = ttk.Frame(self.main_screenshots_section)
        capture_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(capture_header, text="Nueva Captura Exacta", command=self.start_area_capture, width=22).pack(side=tk.LEFT)
        ttk.Button(capture_header, text="Vaciar Capturas", command=self.clear_screenshots_folder, width=18).pack(side=tk.RIGHT)

        if not self.screenshot_regions:
            ttk.Label(self.main_screenshots_section, text="No hay regiones guardadas todavia.").pack(anchor=tk.W, pady=(8, 0))
        else:
            capture_table = ttk.Frame(self.main_screenshots_section)
            capture_table.pack(fill=tk.X, pady=(8, 0))

            ttk.Label(capture_table, text="Captura", width=44).grid(row=0, column=0, sticky=tk.W, padx=4)
            ttk.Label(capture_table, text="Accion", width=12).grid(row=0, column=1, sticky=tk.W, padx=4)

            for idx, (region_name, region_data) in enumerate(self.screenshot_regions.items(), start=1):
                row = ttk.Frame(capture_table, relief=tk.RIDGE, padding=6)
                row.grid(row=idx, column=0, columnspan=2, sticky=tk.EW, pady=3)
                bbox = region_data.get('bbox', [0, 0, 0, 0])
                ttk.Label(row, text=f"{region_name} [{bbox[0]}, {bbox[1]} -> {bbox[2]}, {bbox[3]}]", width=44).grid(row=0, column=0, sticky=tk.W, padx=4)
                ttk.Button(row, text="Capturar", command=lambda rn=region_name: self.capture_screenshot_region(rn), width=12).grid(row=0, column=1, sticky=tk.E, padx=4)
                row.columnconfigure(0, weight=1)

    def refresh_prompt_tasks(self):
        """Actualiza la lista de tareas en la pestaÃ±a de prompts"""
        self.prompt_tasks_listbox.delete(0, tk.END)
        for task_name, task_data in self.tasks.items():
            has_prompt = bool(task_data.get('prompt_template', '').strip())
            status_icon = "P" if has_prompt else "-"
            display_text = f"{status_icon} {task_name}"
            self.prompt_tasks_listbox.insert(tk.END, display_text)

    def on_prompt_task_select(self, event):
        """Maneja la selecciÃ³n de una tarea en la lista de prompts"""
        selection = self.prompt_tasks_listbox.curselection()
        if not selection:
            return

        task_names = list(self.tasks.keys())
        if selection[0] >= len(task_names):
            return

        task_name = task_names[selection[0]]
        task = self.tasks[task_name]

        # Actualizar informaciÃ³n de la tarea seleccionada
        self.selected_task_label.config(text=f"Tarea: {task_name}")

        # Mostrar template del prompt
        prompt_template = task.get('prompt_template', '')
        self.prompt_template_text.config(state=tk.NORMAL)
        self.prompt_template_text.delete(1.0, tk.END)
        if prompt_template:
            self.prompt_template_text.insert(1.0, prompt_template)
        else:
            self.prompt_template_text.insert(1.0, "Esta tarea no tiene un prompt configurado.\nHaz clic en 'Editar Prompt' para crear uno.")
        self.prompt_template_text.config(state=tk.DISABLED)

        # Limpiar Ã¡reas de trabajo
        self.dynamic_content_text.delete(1.0, tk.END)
        self.final_prompt_text.config(state=tk.NORMAL)
        self.final_prompt_text.delete(1.0, tk.END)
        self.final_prompt_text.config(state=tk.DISABLED)

    def edit_task_prompt(self):
        """Abre el editor de prompt para la tarea seleccionada"""
        selection = self.prompt_tasks_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una tarea para editar su prompt")
            return

        task_names = list(self.tasks.keys())
        task_name = task_names[selection[0]]
        task = self.tasks[task_name]

        # Crear ventana de ediciÃ³n de prompt
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title(f"Editor de Prompt: {task_name}")
        prompt_window.geometry("800x600")
        prompt_window.transient(self.root)
        prompt_window.grab_set()

        # Frame principal
        main_frame = ttk.Frame(prompt_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # TÃ­tulo
        title_label = ttk.Label(main_frame, text=f"Editando Prompt para: {task_name}",
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # Instrucciones
        instructions_frame = ttk.LabelFrame(main_frame, text="Instrucciones", padding="10")
        instructions_frame.pack(fill=tk.X, pady=(0, 15))

        instructions_text = """Como crear un prompt dinamico:

1. Escribe tu plantilla de prompt en el area de abajo
2. Usa {CONTENIDO_DINAMICO} donde quieras insertar contenido variable
3. En la pestaña de Prompts, podras pegar contenido especifico y generar el prompt final

Ejemplo:
"Analiza el siguiente boton y determina si esta habilitado:
{CONTENIDO_DINAMICO}

Responde solo: HABILITADO o INHABILITADO"
"""

        instructions_label = ttk.Label(instructions_frame, text=instructions_text,
                                     font=("Arial", 9), justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)

        # Editor de prompt
        ttk.Label(main_frame, text="Plantilla del Prompt:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(10, 5))

        editor_frame = ttk.Frame(main_frame)
        editor_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        prompt_editor = tk.Text(editor_frame, wrap=tk.WORD, font=("Arial", 10))
        scrollbar_editor = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=prompt_editor.yview)
        prompt_editor.configure(yscrollcommand=scrollbar_editor.set)

        prompt_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_editor.pack(side=tk.RIGHT, fill=tk.Y)

        # Cargar prompt existente
        current_prompt = task.get('prompt_template', '')
        if current_prompt:
            prompt_editor.insert(1.0, current_prompt)
        else:
            # Plantilla por defecto
            default_template = f"""Ir a la URL
Hacer click en el captcha
Ver estado del boton
Habilitado continuar
Deshabilitado recargar y tocar captcha
tomar captura de requerimiento
Tomar captura matriz

Estado del boton:
Solo debes contestar utilizando una sola palabra HABILITADO O INHABILITADO
Mira los siguientes ejemplos:

Boton inhabilitado:
<input type="submit" name="ctl00$PlaceContent$Ingresar" value="&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; INGRESAR &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;" id="Ingresar" class="btn btn-default" disabled aria-label="Ingresar">

Boton habilitado:
<input type="submit" name="ctl00$PlaceContent$Ingresar" value="&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; INGRESAR &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;" id="Ingresar" class="btn btn-default" aria-label="Ingresar">

Como esta actualmente el boton real:
{{CONTENIDO_DINAMICO}}"""
            prompt_editor.insert(1.0, default_template)

        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        def save_prompt():
            new_prompt = prompt_editor.get(1.0, tk.END).strip()
            self.tasks[task_name]['prompt_template'] = new_prompt
            self.save_tasks_to_file()
            self.refresh_prompt_tasks()
            prompt_window.destroy()
            messagebox.showinfo("Exito", f"Prompt guardado para la tarea '{task_name}'")

        def preview_prompt():
            current_text = prompt_editor.get(1.0, tk.END).strip()
            preview_text = current_text.replace("{CONTENIDO_DINAMICO}", "[AQUI SE INSERTARA EL CONTENIDO DINAMICO]")

            preview_window = tk.Toplevel(prompt_window)
            preview_window.title("Vista Previa del Prompt")
            preview_window.geometry("600x400")
            preview_window.transient(prompt_window)

            preview_frame = ttk.Frame(preview_window, padding="20")
            preview_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(preview_frame, text="Vista Previa:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

            preview_text_widget = tk.Text(preview_frame, wrap=tk.WORD, font=("Arial", 10), state=tk.DISABLED)
            preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=preview_text_widget.yview)
            preview_text_widget.configure(yscrollcommand=preview_scrollbar.set)

            preview_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            preview_text_widget.config(state=tk.NORMAL)
            preview_text_widget.insert(1.0, preview_text)
            preview_text_widget.config(state=tk.DISABLED)

            ttk.Button(preview_frame, text="Cerrar", command=preview_window.destroy).pack(pady=10)

        ttk.Button(buttons_frame, text="Vista Previa", command=preview_prompt).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Guardar", command=save_prompt).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Cancelar", command=prompt_window.destroy).pack(side=tk.LEFT, padx=5)

    def generate_final_prompt(self):
        """Genera el prompt final combinando la plantilla con el contenido dinamico"""
        selection = self.prompt_tasks_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una tarea primero")
            return

        task_names = list(self.tasks.keys())
        task_name = task_names[selection[0]]
        task = self.tasks[task_name]

        prompt_template = task.get('prompt_template', '')
        if not prompt_template.strip():
            messagebox.showwarning("Advertencia", "Esta tarea no tiene un prompt configurado")
            return

        # Obtener contenido dinÃ¡mico
        dynamic_content = self.dynamic_content_text.get(1.0, tk.END).strip()

        # Generar prompt final
        if "{CONTENIDO_DINAMICO}" in prompt_template:
            if not dynamic_content:
                messagebox.showwarning("Advertencia", "Ingresa contenido dinamico para completar el prompt")
                return
            final_prompt = prompt_template.replace("{CONTENIDO_DINAMICO}", dynamic_content)
        else:
            # Si no hay placeholder, agregar el contenido al final
            final_prompt = prompt_template
            if dynamic_content:
                final_prompt += f"\n\nContenido adicional:\n{dynamic_content}"

        # Mostrar prompt final
        self.final_prompt_text.config(state=tk.NORMAL)
        self.final_prompt_text.delete(1.0, tk.END)
        self.final_prompt_text.insert(1.0, final_prompt)
        self.final_prompt_text.config(state=tk.DISABLED)

        messagebox.showinfo("Exito", "Prompt final generado correctamente")

    def copy_final_prompt(self):
        """Copia el prompt final al portapapeles"""
        final_prompt = self.final_prompt_text.get(1.0, tk.END).strip()

        if not final_prompt:
            messagebox.showwarning("Advertencia", "Primero genera el prompt final")
            return

        # Copiar al portapapeles
        self.root.clipboard_clear()
        self.root.clipboard_append(final_prompt)
        messagebox.showinfo("Exito", "Prompt copiado al portapapeles")

    # ==================== MÃ‰TODOS DEL SERVIDOR HTTP ====================

    def start_http_server(self):
        """Inicia el servidor HTTP"""
        success, message = self.http_server.start_server()

        if success:
            self.server_status = "running"
            self.server_status_label.config(text="Servidor ejecutandose")
            self.server_url_label.config(text=f"URL: http://localhost:{self.http_server.port}")
            self.start_server_btn.config(state="disabled")
            self.stop_server_btn.config(state="normal")
            messagebox.showinfo("Exito", message)
        else:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor: {message}")

    def stop_http_server(self):
        """Detiene el servidor HTTP"""
        success, message = self.http_server.stop_server()

        self.server_status = "stopped"
        self.server_status_label.config(text="Servidor detenido")
        self.server_url_label.config(text="")
        self.start_server_btn.config(state="normal")
        self.stop_server_btn.config(state="disabled")

        if success:
            messagebox.showinfo("Informacion", message)
        else:
            messagebox.showwarning("Advertencia", message)

    def copy_api_examples(self):
        """Copia ejemplos de uso de la API al portapapeles"""
        if not self.http_server.is_running:
            messagebox.showwarning("Advertencia", "El servidor debe estar ejecutandose para copiar ejemplos")
            return

        port = self.http_server.port
        examples = f"""# Ejemplos de uso de la API - Puerto {port}

# Obtener estado del servidor
curl http://localhost:{port}/api/status

# Listar todas las tareas
curl http://localhost:{port}/api/tasks

# Ejecutar una tarea especÃ­fica
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
        messagebox.showinfo("Exito", "Ejemplos copiados al portapapeles")

    def test_api_connection(self):
        """Prueba la conexion con la API"""
        if not self.http_server.is_running:
            messagebox.showwarning("Advertencia", "El servidor debe estar ejecutandose para probar la API")
            return

        try:
            import requests

            # Probar endpoint de estado
            url = f"http://localhost:{self.http_server.port}/api/status"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                message = f"API funcionando correctamente\n\n"
                message += f"Estado: {data['status']}\n"
                message += f"Puerto: {data['server_port']}\n"
                message += f"Tareas disponibles: {data['tasks_count']}\n"
                message += f"Endpoints: {len(data['available_endpoints'])}"

                messagebox.showinfo("Prueba de API", message)
            else:
                messagebox.showerror("Error", f"Error en la API: {response.status_code}")

        except ImportError:
            messagebox.showwarning("Advertencia",
                                 "La libreria 'requests' no esta instalada.\n"
                                 "Instalala con: pip install requests")
        except Exception as e:
            messagebox.showerror("Error", f"Error probando la API: {str(e)}")

    def start_area_capture(self):
        """Inicia la definicion de una region exacta para capturas repetibles"""
        self.status_label.config(text="Selecciona el area exacta a capturar...")
        self.root.withdraw()

        # Crear selector de area
        self.current_area_selector = AreaSelector(self.on_area_captured)

    def on_area_captured(self, filepath, screenshot_image, bbox):
        """Callback cuando se completa la captura inicial y se guarda la region"""
        self.current_area_selector = None
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        if filepath is None or bbox is None:
            self.status_label.config(text="Captura cancelada")
            self.screenshot_label.config(text="")
            return

        next_index = len(self.screenshot_regions) + 1
        region_name = f"captura_{next_index}"
        while region_name in self.screenshot_regions:
            next_index += 1
            region_name = f"captura_{next_index}"

        self.screenshot_regions[region_name] = {
            'bbox': list(bbox),
            'created_at': datetime.now().isoformat(),
            'last_capture': filepath
        }
        self.active_screenshot_region = region_name
        self.save_screenshot_regions_to_file()
        self.refresh_screenshot_regions_list()
        self.refresh_main_panel()

        self.status_label.config(text=f"Region guardada: {region_name}")
        self.screenshot_label.config(text=f"Ultima captura: {os.path.basename(filepath)}")

    def refresh_screenshot_regions_list(self):
        """Actualiza la lista de regiones guardadas"""
        if not hasattr(self, "screenshot_regions_listbox"):
            return

        self.screenshot_regions_listbox.delete(0, tk.END)
        for region_name, region_data in self.screenshot_regions.items():
            bbox = region_data.get('bbox', [0, 0, 0, 0])
            label = f"{region_name} [{bbox[0]}, {bbox[1]} -> {bbox[2]}, {bbox[3]}]"
            self.screenshot_regions_listbox.insert(tk.END, label)

    def get_selected_screenshot_region_name(self):
        """Obtiene el nombre de la region seleccionada"""
        if not hasattr(self, "screenshot_regions_listbox"):
            return None

        selection = self.screenshot_regions_listbox.curselection()
        if not selection:
            return None

        selected_text = self.screenshot_regions_listbox.get(selection[0])
        return selected_text.split(" [", 1)[0]

    def capture_selected_screenshot_region(self):
        """Captura nuevamente la region seleccionada"""
        region_name = self.get_selected_screenshot_region_name()
        if not region_name:
            self.status_label.config(text="Selecciona una region para capturar")
            return

        self.capture_screenshot_region(region_name)

    def capture_screenshot_region(self, region_name):
        """Captura una region guardada por nombre"""
        region_data = self.screenshot_regions.get(region_name)
        if not region_data:
            self.status_label.config(text=f"La region '{region_name}' no existe")
            return

        try:
            bbox = tuple(region_data['bbox'])
            screenshot = ImageGrab.grab(bbox=bbox)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in region_name.lower())
            filename = f"{safe_name}_{timestamp}.png"

            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)

            filepath = os.path.join(screenshots_dir, filename)
            screenshot.save(filepath)

            region_data['last_capture'] = filepath
            self.save_screenshot_regions_to_file()
            self.last_screenshot = filepath
            self.active_screenshot_region = region_name
            self.screenshot_label.config(text=f"Ultima captura: {os.path.basename(filepath)}")
            self.status_label.config(text=f"Captura realizada: {region_name}")
        except Exception as e:
            self.status_label.config(text=f"Error al capturar region: {str(e)}")
            print(f"Error al capturar region: {e}")

    def delete_selected_screenshot_region(self):
        """Elimina la region seleccionada"""
        region_name = self.get_selected_screenshot_region_name()
        if not region_name:
            self.status_label.config(text="Selecciona una region para eliminar")
            return

        self.delete_selected_screenshot_region_by_name(region_name)

    def delete_selected_screenshot_region_by_name(self, region_name):
        """Elimina una region por nombre"""
        if region_name in self.screenshot_regions:
            del self.screenshot_regions[region_name]
            if self.active_screenshot_region == region_name:
                self.active_screenshot_region = None
            self.save_screenshot_regions_to_file()
            self.refresh_screenshot_regions_list()
            self.refresh_main_panel()
            self.status_label.config(text=f"Region eliminada: {region_name}")

    def clear_screenshots_folder(self):
        """Borra todos los archivos de la carpeta screenshots"""
        screenshots_dir = "screenshots"
        deleted_count = 0

        try:
            if os.path.exists(screenshots_dir):
                for entry in os.listdir(screenshots_dir):
                    entry_path = os.path.join(screenshots_dir, entry)
                    if os.path.isfile(entry_path) or os.path.islink(entry_path):
                        os.remove(entry_path)
                        deleted_count += 1
                    elif os.path.isdir(entry_path):
                        shutil.rmtree(entry_path)
                        deleted_count += 1
            else:
                os.makedirs(screenshots_dir)

            self.last_screenshot = None
            self.screenshot_label.config(text="")
            self.status_label.config(text=f"Carpeta screenshots vaciada ({deleted_count} elemento(s))")
            self.refresh_main_panel()
        except Exception as e:
            self.status_label.config(text=f"Error vaciando screenshots: {str(e)}")

    def web_capture_or_select_region(self):
        """Si existe una region activa, la captura; si no, abre el selector nativo"""
        if self.screenshot_regions:
            region_name = self.active_screenshot_region
            if not region_name or region_name not in self.screenshot_regions:
                region_name = next(iter(self.screenshot_regions))
            self.root.after(0, lambda rn=region_name: self.capture_screenshot_region(rn))
            return

        self.root.after(0, self.start_area_capture)
    def play_recording(self):
        """Reproduce la grabacion"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabacion para reproducir")
            return

        self.is_playing = True
        self.play_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.status_label.config(text="Reproduciendo...")

        # Ejecutar reproducciÃ³n en hilo separado
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
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error durante reproduccion: {str(e)}"))
        finally:
            self.is_playing = False
            self.root.after(0, self._finish_playback)

    def _execute_event(self, event):
        """Ejecuta un evento especÃ­fico"""
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
        """Finaliza la reproduccion"""
        self.play_btn.config(state="normal")
        self.record_btn.config(state="normal")
        self.status_label.config(text="Reproduccion completada")

    def clear_recording(self):
        """Limpia la grabacion actual"""
        if messagebox.askyesno("Confirmar", "Estas seguro de que quieres limpiar la grabacion?"):
            self.recorded_events = []
            self.play_btn.config(state="disabled")
            self.status_label.config(text="Grabacion limpiada")
            self.events_label.config(text="Eventos grabados: 0")
            self.refresh_main_panel()

    def save_recording(self):
        """Guarda la grabacion en un archivo y deja una copia en recordings/"""
        if not self.recorded_events:
            messagebox.showwarning("Advertencia", "No hay grabacion para guardar")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Guardar grabacion"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.recorded_events, f, indent=2, ensure_ascii=False)

                os.makedirs(self.recordings_dir, exist_ok=True)
                auto_name = f"grabacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                auto_path = os.path.join(self.recordings_dir, auto_name)
                with open(auto_path, 'w', encoding='utf-8') as f:
                    json.dump(self.recorded_events, f, indent=2, ensure_ascii=False)

                self.refresh_main_panel()
                messagebox.showinfo("Exito", f"Grabacion guardada en: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def load_recording(self):
        """Carga una grabacion desde un archivo"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Cargar grabacion"
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.recorded_events = json.load(f)
                self.play_btn.config(state="normal")
                self.status_label.config(text="Grabacion cargada")
                self.events_label.config(text=f"Eventos grabados: {len(self.recorded_events)}")
                self.refresh_main_panel()
                messagebox.showinfo("Exito", f"Grabacion cargada desde: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar: {str(e)}")

    def run(self):
        """Ejecuta la aplicaciÃ³n"""
        self.root.mainloop()

if __name__ == "__main__":
    app = MouseKeyboardRecorder()
    app.run()


