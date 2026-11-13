"""
Koperfield - Opciones

Ventana para elegir el modo (selectivo o clásico), los atajos de teclado y los
programas que se esconden. Guarda "koperfield_config.json" en su misma carpeta,
que lee Koperfield (.pyw o .exe). Hay que tener los dos en la misma carpeta.
Los cambios se aplican en Koperfield en un par de segundos, sin reiniciar.

Sin dependencias: solo Python 3 en Windows (tkinter viene incluido).
"""
import ctypes
import json
import os
import sys
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox, ttk


def carpeta_app():
    if getattr(sys, "frozen", False):  # si está compilado con PyInstaller
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def sistema_en_espanol():
    """True si el teclado o Windows están en español (de España o de Latinoamérica).

    En los identificadores de idioma de Windows, los 10 bits bajos son el idioma
    principal: 0x0A es español en todas sus variantes (es-ES, es-MX, es-AR, es-419…).
    Si no es español, la interfaz sale en inglés."""
    ESPANOL = 0x0A
    try:
        # Teclado por defecto del usuario (el que tiene al arrancar el programa)
        if (ctypes.windll.user32.GetKeyboardLayout(0) & 0x3FF) == ESPANOL:
            return True
        # Idioma de Windows
        return (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == ESPANOL
    except Exception:
        return False


ES = sistema_en_espanol()


def tr(es, en):
    """Texto en español si Windows está en español; si no, en inglés."""
    return es if ES else en


CARPETA = carpeta_app()
RUTA_CONFIG = os.path.join(CARPETA, "koperfield_config.json")
RUTA_CONFIG_ANTIGUA = os.path.join(CARPETA, "esconder_config.json")

CONFIG_DEFECTO = {
    "modo": "selectivo",
    "icono_bandeja": True,
    "atajos": {
        "esconder": {"mods": ["ctrl"], "vk": 0x20},
        "mostrar": {"mods": ["altgr"], "vk": 0x20},
        "pausa": {"mods": ["ctrl", "shift"], "vk": 0x20},
        "salir": {"mods": ["ctrl", "alt"], "vk": 0x51},
    },
    "navegadores": ["brave"],
    "aplicaciones": ["whatsapp", "discord"],
}
ACCIONES = [
    ("esconder", tr("Esconder", "Hide")),
    ("mostrar", tr("Mostrar", "Show")),
    ("pausa", tr("Pausar / reanudar", "Pause / resume")),
    ("salir", tr("Salir del programa", "Quit program")),
]
ORDEN_MODS = ["ctrl", "shift", "alt", "altgr"]
NOMBRE_MOD = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "altgr": "AltGr"}
MODS_VALIDOS = set(ORDEN_MODS)

# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_INJECTED = 0x10

VK_ESCAPE = 0x1B
VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
VK_LMENU = 0xA4  # Alt izquierdo
VK_RMENU = 0xA5  # Alt derecho (AltGr)
VK_LWIN, VK_RWIN = 0x5B, 0x5C
MODIFICADORES = {VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL,
                 VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN}
CLASES_PROTEGIDAS = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def clase_de(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def titulo_de(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
TH32CS_SNAPPROCESS = 0x2
INVALID_HANDLE = ctypes.c_void_p(-1).value


def nombres_procesos():
    """Diccionario pid -> nombre del .exe (minúsculas) de todos los procesos.

    Usa una "foto" de la lista de procesos de Windows: no abre ningún proceso
    ni lee su memoria, así que no molesta a los anticheats de los juegos."""
    nombres = {}
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return nombres
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            nombres[pe.th32ProcessID] = pe.szExeFile.lower()
            ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        kernel32.CloseHandle(snap)
    return nombres


def programas_abiertos():
    """Lista [(nombre, título)] de los programas con alguna ventana visible ahora mismo."""
    resultado = {}
    yo = kernel32.GetCurrentProcessId()
    exes = nombres_procesos()

    @ENUMPROC
    def cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            titulo = titulo_de(hwnd)
            if not titulo or clase_de(hwnd) in CLASES_PROTEGIDAS:
                return True
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == yo:
                return True
            nombre = normalizar_nombre(exes.get(pid.value, ""))
            if nombre and nombre != "applicationframehost" and nombre not in resultado:
                resultado[nombre] = titulo
        except Exception:
            pass
        return True

    user32.EnumWindows(cb, 0)
    return sorted(resultado.items())


# --------------------------------------------------------------------------
# Utilidades de configuración y de teclas
# --------------------------------------------------------------------------
def normalizar_nombre(texto):
    n = str(texto).strip().strip('"').lower()
    return n[:-4] if n.endswith(".exe") else n


def normalizar_lista(textos):
    """Admite varios nombres por campo separados por comas. Quita vacíos y repetidos."""
    salida = []
    for t in textos:
        for parte in str(t).split(","):
            n = normalizar_nombre(parte)
            if n and n not in salida:
                salida.append(n)
    return salida


def nombre_tecla(vk):
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return "F%d" % (vk - 0x6F)
    if 0x60 <= vk <= 0x69:
        return "Num %d" % (vk - 0x60)
    otros = {
        0x20: tr("Espacio", "Space"), 0x09: "Tab", 0x0D: "Enter", 0x1B: "Esc",
        0x08: tr("Retroceso", "Backspace"), 0x2D: "Insert", 0x2E: tr("Supr", "Delete"),
        0x24: tr("Inicio", "Home"), 0x23: tr("Fin", "End"),
        0x21: tr("Re Pág", "Page Up"), 0x22: tr("Av Pág", "Page Down"),
        0x25: tr("Izquierda", "Left"), 0x26: tr("Arriba", "Up"),
        0x27: tr("Derecha", "Right"), 0x28: tr("Abajo", "Down"), 0xC0: "Ñ / `", 0xBA: "´ / ¨",
        0xBB: "+", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "- / _",
        0xDB: "' / ?", 0xDC: "º / ª", 0xDD: "¡ / ¿", 0xDE: "´", 0xE2: "< / >",
    }
    return otros.get(vk, tr("Tecla", "Key") + " 0x%02X" % vk)


def formato_atajo(mods, vk):
    partes = [NOMBRE_MOD[m] for m in ORDEN_MODS if m in mods]
    partes.append(nombre_tecla(vk))
    return " + ".join(partes)


def nombres_mods(mod_vk):
    """Convierte las teclas modificadoras pulsadas en nombres (ctrl, shift, alt, altgr)."""
    m = set()
    # Al pulsar AltGr, Windows manda además un Ctrl izquierdo "falso": no cuenta como Ctrl
    if VK_RCONTROL in mod_vk or (VK_LCONTROL in mod_vk and VK_RMENU not in mod_vk):
        m.add("ctrl")
    if VK_LSHIFT in mod_vk or VK_RSHIFT in mod_vk:
        m.add("shift")
    if VK_LMENU in mod_vk:
        m.add("alt")
    if VK_RMENU in mod_vk:
        m.add("altgr")
    return [x for x in ORDEN_MODS if x in m]


# Combinaciones que casi todas las aplicaciones usan: se avisa antes de pisarlas
COMUNES = {(frozenset({"ctrl"}), ord(c)) for c in "CVXZYASFWTNPRQOGH"}
COMUNES |= {(frozenset({"alt"}), 0x73), (frozenset({"alt"}), 0x09)}  # Alt+F4, Alt+Tab


def cargar_config():
    cfg = json.loads(json.dumps(CONFIG_DEFECTO))  # copia
    ruta = RUTA_CONFIG
    if not os.path.exists(ruta) and os.path.exists(RUTA_CONFIG_ANTIGUA):
        ruta = RUTA_CONFIG_ANTIGUA  # configuración de la versión anterior
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if datos.get("modo") in ("selectivo", "clasico"):
            cfg["modo"] = datos["modo"]
        cfg["icono_bandeja"] = bool(datos.get("icono_bandeja", True))
        for accion in cfg["atajos"]:
            a = (datos.get("atajos") or {}).get(accion)
            if a and set(a["mods"]) <= MODS_VALIDOS and a["mods"] and 1 <= int(a["vk"]) <= 254:
                cfg["atajos"][accion] = {"mods": list(a["mods"]), "vk": int(a["vk"])}
        if "navegadores" in datos or "aplicaciones" in datos:
            cfg["navegadores"] = normalizar_lista(datos.get("navegadores", []))
            cfg["aplicaciones"] = normalizar_lista(datos.get("aplicaciones", []))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return cfg


# --------------------------------------------------------------------------
# Grabar un atajo pulsando las teclas
# --------------------------------------------------------------------------
def grabar_atajo(root):
    """Abre un cuadro que espera una combinación. Devuelve (mods, vk) o None si se cancela."""
    top = tk.Toplevel(root)
    top.title(tr("Nuevo atajo", "New shortcut"))
    top.transient(root)
    top.resizable(False, False)
    ttk.Label(top, text=tr("Pulsa ahora la combinación de teclas que quieras.\n\n"
                           "Esc (solo) para cancelar.",
                           "Press the key combination you want now.\n\n"
                           "Esc (alone) to cancel."),
              justify="center", padding=24).pack()
    top.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - top.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - top.winfo_height()) // 2
    top.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    estado = {"mods": set(), "res": None, "hecho": False, "hook": None}

    def terminar(res):
        if estado["hook"]:
            user32.UnhookWindowsHookEx(estado["hook"])
            estado["hook"] = None
        estado["res"] = res
        try:
            top.destroy()
        except tk.TclError:
            pass

    @HOOKPROC
    def hook(nCode, wParam, lParam):
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            abajo = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            arriba = wParam in (WM_KEYUP, WM_SYSKEYUP)
            if vk in MODIFICADORES:
                if abajo:
                    estado["mods"].add(vk)
                elif arriba:
                    estado["mods"].discard(vk)
            elif not (kb.flags & LLKHF_INJECTED):
                if abajo:
                    if not estado["hecho"]:
                        estado["hecho"] = True
                        mods = nombres_mods(estado["mods"])
                        res = None if (vk == VK_ESCAPE and not mods) else (mods, vk)
                        root.after(10, lambda: terminar(res))
                    return 1  # la tecla no llega a ninguna otra aplicación
                if arriba and estado["hecho"]:
                    return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    estado["hook"] = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, hook, kernel32.GetModuleHandleW(None), 0)
    if not estado["hook"]:
        top.destroy()
        messagebox.showerror("Error", tr("No se pudo escuchar el teclado.",
                                         "Could not listen to the keyboard."), parent=root)
        return None

    top.protocol("WM_DELETE_WINDOW", lambda: terminar(None))
    root.after(20000, lambda: terminar(None) if estado["hook"] else None)  # seguridad
    top.focus_force()
    root.wait_window(top)
    return estado["res"]


# --------------------------------------------------------------------------
# Ventana principal
# --------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title(tr("Koperfield - Opciones", "Koperfield - Options"))
        root.resizable(False, False)
        poner_icono(root)
        cfg = cargar_config()
        self.atajos = cfg["atajos"]

        main = ttk.Frame(root, padding=14)
        main.grid(sticky="nsew")

        # ---- Modo
        lm = ttk.LabelFrame(main, text=tr("Modo", "Mode"), padding=10)
        lm.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.var_modo = tk.StringVar(value=cfg["modo"])
        ttk.Radiobutton(lm, text=tr("Selectivo: esconde todas las ventanas de los programas de la lista",
                                "Selective: hides every window of the programs in the list"),
                        value="selectivo", variable=self.var_modo, command=self.al_cambiar_modo
                        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(lm, text=tr("Clásico: esconde solo la ventana activa (máximo una)",
                                "Classic: hides only the active window (one at most)"),
                        value="clasico", variable=self.var_modo, command=self.al_cambiar_modo
                        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.var_bandeja = tk.BooleanVar(value=cfg["icono_bandeja"])
        ttk.Checkbutton(lm, text=tr("Mostrar icono en la bandeja (junto al reloj)",
                                 "Show tray icon (next to the clock)"),
                        variable=self.var_bandeja).grid(row=2, column=0, sticky="w", pady=(8, 0))

        # ---- Atajos
        lf = ttk.LabelFrame(main, text=tr("Atajos de teclado (los mismos en los dos modos)",
                                         "Keyboard shortcuts (same for both modes)"), padding=10)
        lf.grid(row=1, column=0, sticky="ew")
        self.etiquetas = {}
        for i, (clave, texto) in enumerate(ACCIONES):
            ttk.Label(lf, text=texto + ":").grid(row=i, column=0, sticky="w", pady=3)
            etiqueta = ttk.Label(lf, width=24, relief="sunken", anchor="center", padding=3)
            etiqueta.grid(row=i, column=1, padx=8)
            ttk.Button(lf, text=tr("Cambiar", "Change"), command=lambda c=clave: self.cambiar_atajo(c)
                       ).grid(row=i, column=2)
            self.etiquetas[clave] = etiqueta
        self.refrescar_atajos()

        # ---- Programas
        lp = ttk.LabelFrame(main, text=tr("Programas a esconder (modo selectivo)",
                                         "Programs to hide (selective mode)"), padding=10)
        lp.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.marco_programas = lp
        self.marco_filas = ttk.Frame(lp)
        self.marco_filas.grid(row=0, column=0, sticky="ew")

        self.var_nav = tk.StringVar(value=", ".join(cfg["navegadores"]))
        self.filas_apps = []
        fila_nav = self.crear_fila(tr("Navegadores:", "Browsers:"), self.var_nav, varios=True,
                                   texto_quitar=tr("Vaciar", "Clear"), quitar=lambda: self.var_nav.set(""))
        self.colocar_fila(fila_nav, 0)
        self.reconstruir_apps(cfg["aplicaciones"])

        self.boton_mas = ttk.Button(lp, text=tr("+ Añadir aplicación", "+ Add application"), command=self.añadir_aplicacion)
        self.boton_mas.grid(row=1, column=0, sticky="w", pady=(6, 0))

        ttk.Label(
            lp, wraplength=470, foreground="#555", justify="left",
            text=tr("Escribe el nombre del programa como aparece en el Administrador de tareas "
                    "(brave, discord…) o usa «Elegir…» con el programa abierto. En Navegadores "
                    "puedes poner varios separados por comas. Los campos vacíos se ignoran. "
                    "«Quitar» borra una aplicación de la lista; nada cambia hasta que pulses Guardar.",
                    "Type the program name as shown in Task Manager (brave, discord…) or use "
                    "\"Choose…\" while the program is open. In Browsers you can enter several, "
                    "separated by commas. Empty fields are ignored. \"Remove\" deletes an "
                    "application from the list; nothing changes until you press Save.")
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        # ---- Botones
        pie = ttk.Frame(main)
        pie.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(pie, text=tr("Guardar", "Save"), command=self.guardar).pack(side="left")
        ttk.Button(pie, text=tr("Valores por defecto", "Defaults"), command=self.por_defecto).pack(side="left", padx=8)
        self.estado = ttk.Label(pie, text="", foreground="#2a7a2a")
        self.estado.pack(side="left", padx=8)

        self.al_cambiar_modo()

    # ---- modo
    def al_cambiar_modo(self):
        """En modo clásico la lista de programas no se usa: se muestra desactivada."""
        estado = ["disabled"] if self.var_modo.get() == "clasico" else ["!disabled"]

        def recorrer(w):
            for hijo in w.winfo_children():
                try:
                    hijo.state(estado)
                except (AttributeError, tk.TclError):
                    pass
                recorrer(hijo)
        recorrer(self.marco_programas)

    # ---- filas de programas
    def crear_fila(self, texto, var, varios=False, texto_quitar=None, quitar=None):
        texto_quitar = texto_quitar or tr("Quitar", "Remove")
        return {
            "var": var,
            "label": ttk.Label(self.marco_filas, text=texto, width=14),
            "entry": ttk.Entry(self.marco_filas, textvariable=var, width=38),
            "elegir": ttk.Button(self.marco_filas, text=tr("Elegir…", "Choose…"),
                                 command=lambda: self.elegir(var, varios)),
            "quitar": ttk.Button(self.marco_filas, text=texto_quitar, width=7, command=quitar),
        }

    def colocar_fila(self, fila_ui, fila):
        fila_ui["label"].grid(row=fila, column=0, sticky="w", pady=3)
        fila_ui["entry"].grid(row=fila, column=1, padx=6)
        fila_ui["elegir"].grid(row=fila, column=2)
        fila_ui["quitar"].grid(row=fila, column=3, padx=(6, 0))

    @staticmethod
    def destruir_fila(fila_ui):
        for clave in ("label", "entry", "elegir", "quitar"):
            fila_ui[clave].destroy()

    def reordenar_apps(self):
        """Vuelve a numerar y colocar las filas de aplicaciones sin huecos."""
        for i, fila_ui in enumerate(self.filas_apps, start=1):
            fila_ui["label"].configure(text=tr("Aplicación %d:", "Application %d:") % i)
            self.colocar_fila(fila_ui, i)

    def añadir_aplicacion(self, valor=""):
        fila_ui = self.crear_fila("", tk.StringVar(value=valor))
        fila_ui["quitar"].configure(command=lambda: self.quitar_aplicacion(fila_ui))
        self.filas_apps.append(fila_ui)
        self.reordenar_apps()
        if hasattr(self, "var_modo"):
            self.al_cambiar_modo()

    def quitar_aplicacion(self, fila_ui):
        self.destruir_fila(fila_ui)
        self.filas_apps.remove(fila_ui)
        self.reordenar_apps()
        self.estado.configure(text=tr("Aplicación quitada (se aplica al guardar)",
                                         "Application removed (applies on save)"), foreground="#555")

    def reconstruir_apps(self, valores):
        for fila_ui in self.filas_apps:
            self.destruir_fila(fila_ui)
        self.filas_apps.clear()
        for n in range(max(3, len(valores))):
            self.añadir_aplicacion(valores[n] if n < len(valores) else "")

    def elegir(self, var, varios):
        nombre = self.dialogo_programas()
        if not nombre:
            return
        if varios:
            actuales = normalizar_lista([var.get()])
            if nombre not in actuales:
                actuales.append(nombre)
            var.set(", ".join(actuales))
        else:
            var.set(nombre)

    def dialogo_programas(self):
        top = tk.Toplevel(self.root)
        top.title(tr("Programas abiertos", "Open programs"))
        top.transient(self.root)
        top.grab_set()
        ttk.Label(top, text=tr("Elige un programa que tengas abierto ahora:",
                                 "Choose a program that is open right now:"),
                  padding=(10, 10, 10, 4)).pack(anchor="w")
        marco = ttk.Frame(top, padding=(10, 0))
        marco.pack(fill="both", expand=True)
        lista = tk.Listbox(marco, width=64, height=14, exportselection=False)
        barra = ttk.Scrollbar(marco, command=lista.yview)
        lista.configure(yscrollcommand=barra.set)
        lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        items = programas_abiertos()
        for nombre, titulo in items:
            lista.insert("end", "%s   —   %s" % (nombre, titulo[:48]))
        elegido = []

        def aceptar(_evento=None):
            sel = lista.curselection()
            if sel:
                elegido.append(items[sel[0]][0])
                top.destroy()

        lista.bind("<Double-Button-1>", aceptar)
        botones = ttk.Frame(top, padding=10)
        botones.pack(fill="x")
        ttk.Button(botones, text=tr("Aceptar", "OK"), command=aceptar).pack(side="right")
        ttk.Button(botones, text=tr("Cancelar", "Cancel"), command=top.destroy).pack(side="right", padx=6)
        self.root.wait_window(top)
        return elegido[0] if elegido else None

    # ---- atajos
    def refrescar_atajos(self):
        for clave, etiqueta in self.etiquetas.items():
            a = self.atajos[clave]
            etiqueta.configure(text=formato_atajo(a["mods"], a["vk"]))

    def cambiar_atajo(self, clave):
        res = grabar_atajo(self.root)
        if not res:
            return
        mods, vk = res
        if not mods:
            messagebox.showwarning(
                tr("Falta un modificador", "Modifier missing"),
                tr("El atajo necesita al menos una tecla Ctrl, Shift, Alt o AltGr; "
                   "si no, bloquearía esa tecla en todos los programas.",
                   "The shortcut needs at least one Ctrl, Shift, Alt or AltGr key; "
                   "otherwise it would block that key in every program."), parent=self.root)
            return
        combo = (frozenset(mods), vk)
        for otra, a in self.atajos.items():
            if otra != clave and (frozenset(a["mods"]), a["vk"]) == combo:
                messagebox.showwarning(
                    tr("Atajo repetido", "Duplicate shortcut"),
                    tr("%s ya se usa para «%s».", "%s is already used for \"%s\".")
                    % (formato_atajo(mods, vk), dict(ACCIONES)[otra]),
                    parent=self.root)
                return
        if combo in COMUNES and not messagebox.askyesno(
                tr("Atajo muy usado", "Common shortcut"),
                tr("%s lo usan muchos programas y dejaría de funcionar en todos ellos "
                   "mientras la app esté activa.\n\n¿Usarlo igualmente?",
                   "%s is used by many programs and would stop working in all of them "
                   "while the app is running.\n\nUse it anyway?") % formato_atajo(mods, vk),
                parent=self.root):
            return
        self.atajos[clave] = {"mods": mods, "vk": vk}
        self.refrescar_atajos()
        self.estado.configure(text="")

    # ---- guardar / restaurar
    def por_defecto(self):
        d = json.loads(json.dumps(CONFIG_DEFECTO))
        self.atajos = d["atajos"]
        self.refrescar_atajos()
        self.var_modo.set(d["modo"])
        self.var_bandeja.set(d["icono_bandeja"])
        self.var_nav.set(", ".join(d["navegadores"]))
        self.reconstruir_apps(d["aplicaciones"])
        self.al_cambiar_modo()
        self.estado.configure(text=tr("Valores por defecto (sin guardar todavía)",
                                         "Defaults (not saved yet)"), foreground="#555")

    def guardar(self):
        navegadores = normalizar_lista([self.var_nav.get()])
        aplicaciones = normalizar_lista([f["var"].get() for f in self.filas_apps])
        for n in navegadores + aplicaciones:
            if len(n) < 3:
                messagebox.showwarning(
                    tr("Nombre demasiado corto", "Name too short"),
                    tr("«%s» es muy corto y podría coincidir con muchos programas.",
                       "\"%s\" is too short and could match many programs.") % n,
                    parent=self.root)
                return
        modo = self.var_modo.get()
        if modo == "selectivo" and not navegadores and not aplicaciones:
            if not messagebox.askyesno(
                    tr("Sin programas", "No programs"),
                    tr("No has puesto ningún programa, así que no se escondería nada. "
                       "¿Guardar igualmente?",
                       "You have not entered any program, so nothing would be hidden. "
                       "Save anyway?"), parent=self.root):
                return
        datos = {
            "modo": modo,
            "icono_bandeja": bool(self.var_bandeja.get()),
            "atajos": {c: {"mods": [m for m in ORDEN_MODS if m in a["mods"]], "vk": a["vk"]}
                       for c, a in self.atajos.items()},
            "navegadores": navegadores,
            "aplicaciones": aplicaciones,
        }
        try:
            tmp = RUTA_CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            os.replace(tmp, RUTA_CONFIG)  # así la app principal nunca lee un archivo a medias
        except OSError as e:
            messagebox.showerror(tr("No se pudo guardar", "Could not save"), str(e), parent=self.root)
            return
        self.estado.configure(text=tr("Guardado. Se aplica en unos segundos.",
                                         "Saved. It applies in a few seconds."), foreground="#2a7a2a")


def poner_icono(ventana):
    candidatos = [os.path.join(CARPETA, "koperfield_opciones.ico"),
                  os.path.join(CARPETA, "recursos", "koperfield_opciones.ico")]
    if getattr(sys, "frozen", False):
        candidatos.insert(0, sys.executable)
        candidatos.insert(0, os.path.join(getattr(sys, "_MEIPASS", CARPETA), "koperfield_opciones.ico"))
    for ruta in candidatos:
        if os.path.exists(ruta):
            try:
                ventana.iconbitmap(default=ruta)
                return
            except tk.TclError:
                pass


def main():
    try:  # pantalla nítida en monitores con escalado
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
