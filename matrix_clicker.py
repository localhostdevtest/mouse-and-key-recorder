import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
from pynput.mouse import Controller, Button
import json
import os

class MatrixClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("Matrix Clicker (3x3)")
        self.root.geometry("600x550")
        
        self.mouse = Controller()
        self.config_file = "matrix_config.json"
        
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        # Instrucciones
        inst_label = ttk.Label(self.root, text="1. Haz clic en 'Capturar (3s)' y pon el mouse donde corresponde.\n2. Guarda las coordenadas.\n3. Pega la secuencia con formato (ej: 1x2 1x3 3x3) y haz clic en Ejecutar.", justify=tk.CENTER)
        inst_label.pack(pady=10)

        # Frame for 3x3 Matrix
        matrix_frame = ttk.LabelFrame(self.root, text="Coordenadas de la Matriz (X, Y)", padding="10")
        matrix_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # Configure columns config
        matrix_frame.columnconfigure(0, weight=1)
        matrix_frame.columnconfigure(1, weight=1)
        matrix_frame.columnconfigure(2, weight=1)

        self.entries = {}
        
        for r in range(1, 4):
            for c in range(1, 4):
                key = f"{r}x{c}"
                
                cell_frame = ttk.Frame(matrix_frame, borderwidth=1, relief="groove", padding=5)
                cell_frame.grid(row=r-1, column=c-1, padx=5, pady=5, sticky="nsew")
                
                ttk.Label(cell_frame, text=f"Item: {key}", font=("Arial", 10, "bold")).pack()
                
                entry_var = tk.StringVar()
                entry = ttk.Entry(cell_frame, textvariable=entry_var, width=12, justify="center")
                entry.pack(pady=5)
                
                btn = ttk.Button(cell_frame, text="Capturar (3s)", command=lambda k=key, var=entry_var: self.capture_coords(k, var))
                btn.pack()
                
                self.entries[key] = entry_var

        # Sequence Execution Frame
        exec_frame = ttk.LabelFrame(self.root, text="Ejecutar Secuencia", padding="10")
        exec_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(exec_frame, text="Secuencia (separada por espacios):").pack(anchor=tk.W)
        self.sequence_var = tk.StringVar()
        self.sequence_entry = ttk.Entry(exec_frame, textvariable=self.sequence_var, font=("Arial", 11))
        self.sequence_entry.pack(fill=tk.X, pady=5)
        
        btn_frame = ttk.Frame(exec_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.guardar_btn = ttk.Button(btn_frame, text="💾 Guardar Coordenadas", command=self.save_config)
        self.guardar_btn.pack(side=tk.LEFT, padx=5)
        
        self.ejecutar_btn = ttk.Button(btn_frame, text="▶ Ejecutar Secuencia", command=self.execute_sequence)
        self.ejecutar_btn.pack(side=tk.RIGHT, padx=5)
        
        self.status_var = tk.StringVar()
        self.status_var.set("ESTADO: Listo")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, font=("Arial", 10, "bold"), foreground="blue")
        self.status_label.pack(pady=5)

    def capture_coords(self, key, var):
        def task():
            # Desactivar botones temporalmente
            for widget in self.root.winfo_children():
                widget.config(cursor="wait")

            for i in range(3, 0, -1):
                self.status_var.set(f"ESTADO: Capturando {key} en {i} segundos... (Mueve el mouse al lugar)")
                self.root.update()
                time.sleep(1)
            
            x, y = self.mouse.position
            var.set(f"{int(x)}, {int(y)}")
            self.status_var.set(f"ESTADO: Coordenadas guardadas para {key} -> ({int(x)}, {int(y)})")
            
            for widget in self.root.winfo_children():
                widget.config(cursor="")
            self.root.update()
            
        threading.Thread(target=task, daemon=True).start()

    def save_config(self):
        data = {k: v.get() for k, v in self.entries.items()}
        try:
            with open(self.config_file, "w") as f:
                json.dump(data, f)
            self.status_var.set(f"ESTADO: Configuración guardada en {self.config_file} exitosamente!")
        except Exception as e:
            self.status_var.set(f"ESTADO: Error al guardar - {str(e)}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in self.entries:
                            self.entries[k].set(v)
                self.status_var.set("ESTADO: Coordenadas cargadas desde el archivo anterior.")
            except Exception as e:
                self.status_var.set(f"ESTADO: Error cargando config - {str(e)}")

    def execute_sequence(self):
        seq = self.sequence_var.get().strip()
        if not seq:
            self.status_var.set("ESTADO: Por favor, ingresa una secuencia.")
            return
            
        items = seq.split()
        
        self.ejecutar_btn.state(['disabled'])
        
        def task():
            for item in items:
                if item in self.entries:
                    val = self.entries[item].get()
                    if val and "," in val:
                        try:
                            x, y = map(int, val.replace(" ", "").split(","))
                            self.status_var.set(f"ESTADO: Clickeando en {item} ({x}, {y})...")
                            self.root.update()
                            
                            # Mover y clickear
                            self.mouse.position = (x, y)
                            time.sleep(0.2) # Pausa para que el SO registre el movimiento
                            self.mouse.click(Button.left)
                            time.sleep(0.5) # Pausa entre cada click de la secuencia
                            
                        except ValueError:
                            print(f"Coordenadas inválidas para {item}")
                else:
                    print(f"Item no reconocido en la secuencia: {item}")
                    
            self.status_var.set("ESTADO: Secuencia completada exitosamente.")
            self.root.after(0, lambda: self.ejecutar_btn.state(['!disabled']))
            
        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MatrixClicker(root)
    root.mainloop()
