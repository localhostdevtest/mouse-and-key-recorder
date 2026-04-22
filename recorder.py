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

class MouseKeyboardRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Grabador de Mouse y Teclado")
        self.root.geometry("450x350")
        self.root.resizable(False, False)

        # Variables de estado
        self.is_recording = False
        self.is_playing = False
        self.recorded_events = []
        self.start_time = None
        self.last_screenshot = None

        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None

        # Controladores para reproducción
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.setup_ui()

    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Título
        title_label = ttk.Label(main_frame, text="Grabador de Mouse y Teclado",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Botones principales
        self.record_btn = ttk.Button(main_frame, text="🔴 Grabar",
                                   command=self.start_recording, width=15)
        self.record_btn.grid(row=1, column=0, padx=(0, 10), pady=5)

        self.stop_btn = ttk.Button(main_frame, text="⏹️ Parar",
                                 command=self.stop_recording, width=15, state="disabled")
        self.stop_btn.grid(row=1, column=1, padx=(10, 0), pady=5)

        self.play_btn = ttk.Button(main_frame, text="▶️ Reproducir",
                                 command=self.play_recording, width=15, state="disabled")
        self.play_btn.grid(row=2, column=0, padx=(0, 10), pady=5)

        self.clear_btn = ttk.Button(main_frame, text="🗑️ Limpiar",
                                  command=self.clear_recording, width=15)
        self.clear_btn.grid(row=2, column=1, padx=(10, 0), pady=5)

        # Botón de captura de área
        self.screenshot_btn = ttk.Button(main_frame, text="📸 Capturar Área",
                                       command=self.start_area_capture, width=32)
        self.screenshot_btn.grid(row=3, column=0, columnspan=2, pady=10)

        # Separador
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        # Botones de archivo
        self.save_btn = ttk.Button(main_frame, text="💾 Guardar Grabación",
                                 command=self.save_recording, width=32)
        self.save_btn.grid(row=5, column=0, columnspan=2, pady=5)

        self.load_btn = ttk.Button(main_frame, text="📁 Cargar Grabación",
                                 command=self.load_recording, width=32)
        self.load_btn.grid(row=6, column=0, columnspan=2, pady=5)

        # Estado
        self.status_label = ttk.Label(main_frame, text="Listo para grabar",
                                    font=("Arial", 10))
        self.status_label.grid(row=7, column=0, columnspan=2, pady=(20, 0))

        # Información de eventos
        self.events_label = ttk.Label(main_frame, text="Eventos grabados: 0",
                                    font=("Arial", 9))
        self.events_label.grid(row=8, column=0, columnspan=2, pady=5)

        # Label para mostrar último screenshot
        self.screenshot_label = ttk.Label(main_frame, text="",
                                        font=("Arial", 9), foreground="blue")
        self.screenshot_label.grid(row=9, column=0, columnspan=2, pady=5)

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