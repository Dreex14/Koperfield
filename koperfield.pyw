"""
Koperfield - esconder ventanas en Windows

Dos modos (se eligen en "Koperfield Options"):
  * Selectivo: esconde de golpe todas las ventanas de los programas de la lista.
  * Clásico:   esconde solo la ventana activa, como máximo una.

Atajos por defecto (se cambian en Opciones):
  Ctrl + Espacio             -> esconde
  AltGr + Espacio            -> muestra
  Ctrl + Shift + Espacio     -> pausa / reanuda
  Ctrl + Alt(izq) + Q        -> sale (y muestra lo escondido)

La configuración está en "koperfield_config.json" (misma carpeta) y se aplica
sola en un par de segundos, sin reiniciar.

Robustez frente a suspensión / hibernación / bloqueo:
  * El hook de teclado vive en su propio hilo y se reinstala al volver de la
    suspensión, al desbloquear la sesión y cada minuto (Windows lo quita sin
    avisar si alguna vez tarda en responder).
  * Las teclas modificadoras se comprueban contra el estado real del teclado,
    así un Ctrl/Win "atascado" (soltado en la pantalla de bloqueo) no bloquea
    los atajos.
  * Las ventanas se esconden/muestran sin esperar a programas colgados.
  * Icono en la bandeja con "Mostrar escondidas" por si algo falla.
  * La lista de escondidas se guarda en disco: si el programa se cierra de
    golpe, al volver a abrirlo se muestran.

Sin dependencias: solo Python 3 en Windows.
"""
import atexit
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes


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
RUTA_ESCONDIDAS = os.path.join(CARPETA, "koperfield_escondidas.json")

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
MODS_VALIDOS = {"ctrl", "shift", "alt", "altgr"}
MODOS = ("selectivo", "clasico")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", wintypes.DWORD * 4),
        ("hBalloonIcon", wintypes.HICON),
    ]


# Tipos explícitos para que todo funcione bien en Python de 64 bits
user32.GetForegroundWindow.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsHungAppWindow.argtypes = [wintypes.HWND]
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.FlashWindowEx.argtypes = [ctypes.POINTER(FLASHWINFO)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                wintypes.UINT, wintypes.UINT]
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wintypes.HICON
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = ctypes.c_void_p
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
                                   ctypes.POINTER(wintypes.HICON), wintypes.UINT]
shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
shell32.ShellExecuteW.restype = ctypes.c_void_p
wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
wtsapi32.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINNOACTIVE = 7  # mostrar minimizada, sin activar
SW_SHOWNA = 8           # mostrar en su estado actual (normal/maximizada), sin activar
FLASHW_STOP = 0
ERROR_ALREADY_EXISTS = 183

WH_KEYBOARD_LL = 13
WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_TIMER = 0x0113
WM_POWERBROADCAST = 0x0218
WM_WTSSESSION_CHANGE = 0x02B1
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
WM_QUIT = 0x0012
WM_APP = 0x8000
LLKHF_INJECTED = 0x10
PM_NOREMOVE = 0

PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
NOTIFY_FOR_THIS_SESSION = 0

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
MF_STRING, MF_GRAYED, MF_CHECKED, MF_SEPARATOR = 0, 1, 8, 0x800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
SM_CXSMICON, SM_CYSMICON = 49, 50
IDI_APPLICATION = 32512

# Mensajes que el hook (otro hilo) le manda a la ventana oculta del hilo principal
ACCION_ESCONDER = WM_APP + 1
ACCION_MOSTRAR = WM_APP + 2
ACCION_PAUSA = WM_APP + 3
ACCION_SALIR = WM_APP + 5
WM_BANDEJA = WM_APP + 20
# Mensaje para el hilo del hook: vuelve a instalarlo y limpia el estado de teclas
HOOK_REINSTALAR = WM_APP + 30

VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
VK_LMENU = 0xA4  # Alt izquierdo
VK_RMENU = 0xA5  # Alt derecho (AltGr)
VK_LWIN, VK_RWIN = 0x5B, 0x5C
MODIFICADORES = {VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL,
                 VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN}

# Ventanas del sistema que nunca se deben esconder
CLASES_PROTEGIDAS = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                     "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow"}
CLASE_OCULTA = "KoperfieldVentanaOculta"

REINSTALAR_CADA_MS = 60_000     # reinstala el hook cada minuto por si Windows lo quitó
SALTO_SUSPENSION_S = 10         # si un tic de 2 s llega tan tarde, venimos de una suspensión

# Configuración activa (se cambia entera de golpe al recargar)
atajos = {}          # acción -> (frozenset de modificadores, vk)
programas = ()       # nombres de programas (minúsculas, sin .exe)
modo = "selectivo"
icono_bandeja = True
ultima_mtime = None  # fecha del archivo de configuración que se cargó

# Compartido entre hilos (asignaciones simples, atómicas en Python)
pausado = False
hwnd_oculta = None
hilo_hook_id = 0

# Estado del hook (solo se toca desde el hilo del hook)
tragando_vk = None   # para bloquear también el "soltar" y el autorepetir de un atajo ya procesado
mod_down = set()     # modificadores pulsados, seguidos a partir de los eventos del hook
hook_actual = None

# Estado del hilo principal
escondidas = []      # ventanas escondidas, la de más arriba primero
icono_en_bandeja = False
hicono = None
ultimo_tic = 0.0
MSG_TASKBAR_CREATED = 0


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
def normalizar_nombre(texto):
    n = str(texto).strip().strip('"').lower()
    return n[:-4] if n.endswith(".exe") else n


def ruta_config_lectura():
    if os.path.exists(RUTA_CONFIG):
        return RUTA_CONFIG
    if os.path.exists(RUTA_CONFIG_ANTIGUA):  # configuración de la versión anterior
        return RUTA_CONFIG_ANTIGUA
    return RUTA_CONFIG


def leer_config():
    with open(ruta_config_lectura(), encoding="utf-8") as f:
        datos = json.load(f)
    return interpretar_config(datos)


def interpretar_config(datos):
    res_atajos = {}
    for accion, defecto in CONFIG_DEFECTO["atajos"].items():
        a = (datos.get("atajos") or {}).get(accion) or defecto
        try:
            mods = frozenset(a["mods"])
            vk = int(a["vk"])
            if not mods or not mods <= MODS_VALIDOS or not 1 <= vk <= 254:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            mods, vk = frozenset(defecto["mods"]), defecto["vk"]
        res_atajos[accion] = (mods, vk)

    nombres = []
    for clave in ("navegadores", "aplicaciones"):
        for n in datos.get(clave, []):
            n = normalizar_nombre(n)
            if n and n not in nombres:
                nombres.append(n)
    m = datos.get("modo", "selectivo")
    if m not in MODOS:
        m = "selectivo"
    return res_atajos, tuple(nombres), m, bool(datos.get("icono_bandeja", True))


def aplicar_config(nuevos_atajos, nuevos_programas, nuevo_modo, nuevo_icono):
    global atajos, programas, modo, icono_bandeja
    atajos = nuevos_atajos
    programas = nuevos_programas
    modo = nuevo_modo
    icono_bandeja = nuevo_icono


def cargar_al_arrancar():
    global ultima_mtime
    try:
        aplicar_config(*leer_config())
        ultima_mtime = os.path.getmtime(ruta_config_lectura())
    except (OSError, ValueError, AttributeError, TypeError):
        aplicar_config(*interpretar_config(CONFIG_DEFECTO))


def recargar_si_cambio():
    """Se llama cada pocos segundos: si el archivo cambió, carga la configuración nueva."""
    global ultima_mtime
    try:
        ruta = ruta_config_lectura()
        mtime = os.path.getmtime(ruta)
        if mtime == ultima_mtime:
            return
        nuevos = leer_config()
        aplicar_config(*nuevos)
        ultima_mtime = mtime
        actualizar_bandeja()
    except (OSError, ValueError, AttributeError, TypeError):
        pass  # archivo a medio escribir o roto: se queda la configuración anterior


# --------------------------------------------------------------------------
# Lista de escondidas en disco (por si el programa se cierra de golpe)
# --------------------------------------------------------------------------
def pid_de(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def guardar_escondidas():
    try:
        datos = [{"hwnd": int(h), "pid": pid_de(h)} for h in escondidas if user32.IsWindow(h)]
        if not datos:
            if os.path.exists(RUTA_ESCONDIDAS):
                os.remove(RUTA_ESCONDIDAS)
            return
        tmp = RUTA_ESCONDIDAS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        os.replace(tmp, RUTA_ESCONDIDAS)
    except OSError:
        pass


def recuperar_escondidas_anteriores():
    """Si una ejecución anterior se cerró sin mostrar sus ventanas, las muestra ahora."""
    try:
        with open(RUTA_ESCONDIDAS, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return
    for d in datos:
        try:
            h = int(d["hwnd"])
            # el pid evita tocar otra ventana que haya heredado el mismo número
            if user32.IsWindow(h) and pid_de(h) == int(d["pid"]) and not user32.IsWindowVisible(h):
                user32.ShowWindowAsync(h, SW_SHOWMINNOACTIVE if user32.IsIconic(h) else SW_SHOWNA)
        except (KeyError, TypeError, ValueError):
            pass
    try:
        os.remove(RUTA_ESCONDIDAS)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Utilidades de ventanas
# --------------------------------------------------------------------------
mutex_unico = None  # se guarda para que el bloqueo dure mientras el programa esté abierto


def ya_esta_abierta():
    """True si ya hay otra copia de este programa en marcha (dos hooks se pisarían)."""
    global mutex_unico
    mutex_unico = kernel32.CreateMutexW(None, False, "Local\\Koperfield_UnaSolaInstancia")
    return ctypes.get_last_error() == ERROR_ALREADY_EXISTS


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


def detener_parpadeo(hwnd):
    """Quita el parpadeo naranja del botón de la barra de tareas."""
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_STOP, 0, 0)
    user32.FlashWindowEx(ctypes.byref(info))


def mostrar_u_ocultar(hwnd, comando):
    # Con un programa colgado (pasa a menudo justo al volver de la suspensión)
    # ShowWindow se quedaría esperando; ShowWindowAsync no espera nunca.
    if user32.IsHungAppWindow(hwnd):
        user32.ShowWindowAsync(hwnd, comando)
    else:
        user32.ShowWindow(hwnd, comando)


def es_objetivo(hwnd, cache_exe, lista):
    """True si es una ventana visible (aunque esté minimizada) de alguno de los programas."""
    if not user32.IsWindowVisible(hwnd):
        return False
    titulo = titulo_de(hwnd)
    if not titulo:  # las ventanas auxiliares/invisibles de Chromium no tienen título
        return False
    clase = clase_de(hwnd)
    if clase in CLASES_PROTEGIDAS:
        return False

    pid = pid_de(hwnd)
    exe = cache_exe.get(pid, "")
    nombre = exe[:-4] if exe.endswith(".exe") else exe

    if nombre and any(nombre.startswith(p) for p in lista):
        return True
    # Apps de la Microsoft Store (p. ej. WhatsApp antiguo) viven dentro de ApplicationFrameHost
    if exe == "applicationframehost.exe" and clase == "ApplicationFrameWindow":
        t = titulo.lower()
        return any(p in t for p in lista)
    return False


def ventanas_objetivo():
    """Todas las ventanas visibles de los programas elegidos, de arriba abajo en el orden Z."""
    encontradas = []
    lista = programas
    if not lista:
        return encontradas
    cache_exe = nombres_procesos()

    @ENUMPROC
    def cb(hwnd, _lparam):
        try:
            if es_objetivo(hwnd, cache_exe, lista):
                encontradas.append(hwnd)
        except Exception:
            pass
        return True  # seguir enumerando

    user32.EnumWindows(cb, 0)
    return encontradas


def traer_al_frente(hwnd):
    # Windows no deja a cualquier programa quitarle el foco a otro: en ese caso
    # solo hace parpadear el botón en naranja. Enlazando nuestro hilo con el de la
    # ventana activa sí se permite pasar la ventana al frente.
    mi_hilo = kernel32.GetCurrentThreadId()
    activa = user32.GetForegroundWindow()
    hilo_activa = user32.GetWindowThreadProcessId(activa, None) if activa else 0
    enlazado = bool(hilo_activa and hilo_activa != mi_hilo
                    and not user32.IsHungAppWindow(activa)
                    and user32.AttachThreadInput(mi_hilo, hilo_activa, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if enlazado:
            user32.AttachThreadInput(mi_hilo, hilo_activa, False)
    detener_parpadeo(hwnd)


# --------------------------------------------------------------------------
# Acciones (se ejecutan en el hilo principal)
# --------------------------------------------------------------------------
def limpiar_escondidas():
    """Quita de la lista las ventanas que se cerraron mientras estaban escondidas."""
    global escondidas
    escondidas = [h for h in escondidas if user32.IsWindow(h)]


def esconder():
    global escondidas
    limpiar_escondidas()
    if modo == "clasico":
        # Solo la ventana activa y como máximo una escondida.
        # Si la que estaba escondida volvió a aparecer sola, ya no cuenta.
        if any(not user32.IsWindowVisible(h) for h in escondidas):
            return
        escondidas = []
        hwnd = user32.GetForegroundWindow()
        if (not hwnd or hwnd == hwnd_oculta or clase_de(hwnd) in CLASES_PROTEGIDAS
                or not user32.IsWindowVisible(hwnd)):
            return
        nuevas = [hwnd]
    else:
        nuevas = [h for h in ventanas_objetivo() if h not in escondidas]
    for h in nuevas:
        detener_parpadeo(h)
        mostrar_u_ocultar(h, SW_HIDE)
    escondidas = nuevas + escondidas
    guardar_escondidas()
    actualizar_bandeja()


def mostrar_todas():
    global escondidas
    vivas = [h for h in escondidas if user32.IsWindow(h)]
    escondidas = []

    # De abajo arriba, para conservar el orden en que estaban apiladas.
    # Cada una vuelve a su estado (las minimizadas siguen minimizadas).
    for h in reversed(vivas):
        mostrar_u_ocultar(h, SW_SHOWMINNOACTIVE if user32.IsIconic(h) else SW_SHOWNA)
        detener_parpadeo(h)

    # Le damos el foco a la que estaba más arriba (si no está minimizada)
    for h in vivas:
        if not user32.IsIconic(h):
            traer_al_frente(h)
            break
    guardar_escondidas()
    actualizar_bandeja()


def abrir_opciones():
    # "Koperfield Opciones.exe" es el nombre de la versión anterior
    for nombre in ("Koperfield Options.exe", "Koperfield Opciones.exe", "koperfield_opciones.pyw"):
        ruta = os.path.join(CARPETA, nombre)
        if os.path.exists(ruta):
            shell32.ShellExecuteW(None, "open", ruta, None, CARPETA, SW_SHOWNORMAL)
            return


# --------------------------------------------------------------------------
# Icono de la bandeja
# --------------------------------------------------------------------------
def cargar_icono():
    hi = wintypes.HICON()
    if getattr(sys, "frozen", False):
        if shell32.ExtractIconExW(sys.executable, 0, None, ctypes.byref(hi), 1) and hi.value:
            return hi.value
    for ruta in (os.path.join(CARPETA, "koperfield.ico"),
                 os.path.join(CARPETA, "recursos", "koperfield.ico")):
        if os.path.exists(ruta):
            h = user32.LoadImageW(None, ruta, IMAGE_ICON, user32.GetSystemMetrics(SM_CXSMICON),
                                  user32.GetSystemMetrics(SM_CYSMICON), LR_LOADFROMFILE)
            if h:
                return h
    return user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))


def datos_icono():
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd_oculta
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_BANDEJA
    nid.hIcon = hicono
    estado = tr("en pausa", "paused") if pausado else tr("activo", "active")
    if modo == "clasico":
        texto = "Koperfield - %s (%s)" % (estado, tr("modo clásico", "classic mode"))
    else:
        texto = "Koperfield - %s (%s)" % (estado, tr("modo selectivo", "selective mode"))
    n = len([h for h in escondidas if user32.IsWindow(h)])
    if n:
        texto += "\n%d %s" % (n, tr("escondida" if n == 1 else "escondidas",
                                    "hidden window" if n == 1 else "hidden windows"))
    nid.szTip = texto[:127]
    return nid


def actualizar_bandeja(forzar_alta=False):
    """Pone, quita o actualiza el icono de la bandeja según la configuración."""
    global icono_en_bandeja
    if not hwnd_oculta:
        return
    if not icono_bandeja:
        if icono_en_bandeja:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(datos_icono()))
            icono_en_bandeja = False
        return
    nid = datos_icono()
    if icono_en_bandeja and not forzar_alta:
        if shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)):
            return
    icono_en_bandeja = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))


def quitar_bandeja():
    global icono_en_bandeja
    if icono_en_bandeja:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(datos_icono()))
        icono_en_bandeja = False


def menu_bandeja():
    global pausado
    limpiar_escondidas()
    n = len(escondidas)
    menu = user32.CreatePopupMenu()
    user32.AppendMenuW(menu, MF_STRING | (0 if n else MF_GRAYED), 1,
                       tr("Mostrar escondidas (%d)", "Show hidden windows (%d)") % n)
    user32.AppendMenuW(menu, MF_STRING, 2, tr("Reanudar", "Resume") if pausado
                       else tr("Pausar", "Pause"))
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if modo == "selectivo" else 0), 5,
                       tr("Modo selectivo", "Selective mode"))
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if modo == "clasico" else 0), 6,
                       tr("Modo clásico (una ventana)", "Classic mode (one window)"))
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING, 3, tr("Opciones…", "Options…"))
    user32.AppendMenuW(menu, MF_STRING, 4, tr("Salir", "Quit"))
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetForegroundWindow(hwnd_oculta)  # si no, el menú no se cierra al hacer clic fuera
    cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
                                pt.x, pt.y, 0, hwnd_oculta, None)
    user32.PostMessageW(hwnd_oculta, WM_NULL, 0, 0)
    user32.DestroyMenu(menu)
    if cmd == 1:
        mostrar_todas()
    elif cmd == 2:
        pausado = not pausado
        actualizar_bandeja()
    elif cmd == 3:
        abrir_opciones()
    elif cmd == 4:
        user32.DestroyWindow(hwnd_oculta)
    elif cmd in (5, 6):
        cambiar_modo("selectivo" if cmd == 5 else "clasico")


def cambiar_modo(nuevo):
    """Guarda el modo en el archivo de configuración (lo mismo que hace Opciones)."""
    global modo, ultima_mtime
    try:
        with open(ruta_config_lectura(), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        datos = json.loads(json.dumps(CONFIG_DEFECTO))
    datos["modo"] = nuevo
    try:
        tmp = RUTA_CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        os.replace(tmp, RUTA_CONFIG)
        ultima_mtime = os.path.getmtime(RUTA_CONFIG)
    except OSError:
        pass
    modo = nuevo
    actualizar_bandeja()


# --------------------------------------------------------------------------
# Hook de teclado (en su propio hilo): solo decide y avisa
# --------------------------------------------------------------------------
def esta_pulsada(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def mods_actuales():
    # Si un modificador se soltó en la pantalla de bloqueo o durante la suspensión,
    # el hook nunca vio el "soltar": lo comprobamos contra el estado real del teclado.
    for vk in list(mod_down):
        if not esta_pulsada(vk):
            mod_down.discard(vk)
    m = set()
    # Al pulsar AltGr, Windows manda además un Ctrl izquierdo "falso": no cuenta como Ctrl
    if VK_RCONTROL in mod_down or (VK_LCONTROL in mod_down and VK_RMENU not in mod_down):
        m.add("ctrl")
    if VK_LSHIFT in mod_down or VK_RSHIFT in mod_down:
        m.add("shift")
    if VK_LMENU in mod_down:
        m.add("alt")
    if VK_RMENU in mod_down:
        m.add("altgr")
    if VK_LWIN in mod_down or VK_RWIN in mod_down:
        m.add("win")
    return frozenset(m)


def enviar(accion, valor=0):
    if hwnd_oculta:
        user32.PostMessageW(hwnd_oculta, accion, valor or 0, 0)


def procesar(vk):
    """Decide qué hacer con una pulsación. Devuelve True si hay que bloquearla."""
    global pausado

    mods = mods_actuales()
    if "win" in mods:
        return False
    combo = (mods, vk)

    if combo == atajos["salir"]:
        enviar(ACCION_SALIR)
        return True

    if combo == atajos["pausa"]:
        pausado = not pausado
        enviar(ACCION_PAUSA, 1 if pausado else 0)
        return True

    if pausado:  # en pausa los atajos pasan tal cual a la aplicación
        return False

    if combo == atajos["mostrar"]:
        enviar(ACCION_MOSTRAR)
        return True

    if combo == atajos["esconder"]:
        enviar(ACCION_ESCONDER)
        return True

    return False


@HOOKPROC
def hook_teclado(nCode, wParam, lParam):
    global tragando_vk
    try:
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            abajo = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            arriba = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if vk in MODIFICADORES:
                # Seguimos nosotros mismos qué modificadores están pulsados (AltGr incluido)
                if abajo:
                    mod_down.add(vk)
                elif arriba:
                    mod_down.discard(vk)
            elif not (kb.flags & LLKHF_INJECTED):
                if tragando_vk is not None and vk == tragando_vk:
                    if arriba:
                        tragando_vk = None
                    return 1  # autorepetición y "soltar" de un atajo ya procesado
                if abajo and procesar(vk):
                    tragando_vk = vk
                    return 1
    except Exception:
        pass  # pase lo que pase, la tecla tiene que seguir su camino
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def instalar_hook(limpiar=False):
    """Instala un hook nuevo y quita el anterior. Con limpiar=True olvida además las
    teclas que creíamos pulsadas (tras suspensión o bloqueo nos perdimos los "soltar")."""
    global hook_actual, tragando_vk
    nuevo = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_teclado, kernel32.GetModuleHandleW(None), 0)
    if nuevo:
        viejo, hook_actual = hook_actual, nuevo
        if viejo:
            user32.UnhookWindowsHookEx(viejo)
    if limpiar:
        mod_down.clear()
        tragando_vk = None
    return bool(nuevo)


def bucle_hook(listo):
    """Hilo dedicado al hook: así nunca espera a que el hilo principal esconda ventanas."""
    global hilo_hook_id
    hilo_hook_id = kernel32.GetCurrentThreadId()
    msg = wintypes.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)  # crea la cola de mensajes
    ok = instalar_hook()
    listo.set()
    if not ok:
        return
    user32.SetTimer(None, 0, REINSTALAR_CADA_MS, None)
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == HOOK_REINSTALAR:
            instalar_hook(limpiar=True)
        elif msg.message == WM_TIMER:
            instalar_hook()
        else:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    if hook_actual:
        user32.UnhookWindowsHookEx(hook_actual)


def pedir_reinstalar_hook():
    if hilo_hook_id:
        user32.PostThreadMessageW(hilo_hook_id, HOOK_REINSTALAR, 0, 0)


# --------------------------------------------------------------------------
# Ventana oculta del hilo principal: recibe acciones, temporizador, avisos de
# suspensión/bloqueo de Windows y los clics del icono de la bandeja
# --------------------------------------------------------------------------
def al_volver():
    """Al volver de suspensión/hibernación/bloqueo: hook nuevo y bandeja otra vez."""
    pedir_reinstalar_hook()
    actualizar_bandeja(forzar_alta=True)


@WNDPROC
def proc_ventana(hwnd, msg, wparam, lparam):
    global ultimo_tic
    try:
        if msg == ACCION_ESCONDER:
            esconder()
            return 0
        if msg == ACCION_MOSTRAR:
            mostrar_todas()
            return 0
        if msg == ACCION_PAUSA:
            actualizar_bandeja()
            return 0
        if msg == ACCION_SALIR:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_TIMER:
            ahora = time.time()
            if ultimo_tic and ahora - ultimo_tic > SALTO_SUSPENSION_S:
                al_volver()  # el reloj saltó: el equipo estuvo dormido
            ultimo_tic = ahora
            recargar_si_cambio()
            return 0
        if msg == WM_POWERBROADCAST:
            if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                al_volver()
            return 1
        if msg == WM_WTSSESSION_CHANGE:
            if wparam in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
                al_volver()
            return 0
        if msg == WM_BANDEJA:
            evento = lparam & 0xFFFF
            if evento in (WM_RBUTTONUP, WM_CONTEXTMENU):
                menu_bandeja()
            elif evento == WM_LBUTTONDBLCLK:
                mostrar_todas()
            return 0
        if MSG_TASKBAR_CREATED and msg == MSG_TASKBAR_CREATED:
            actualizar_bandeja(forzar_alta=True)  # el Explorador se reinició
            return 0
        if msg == WM_QUERYENDSESSION:
            mostrar_todas()  # Windows se apaga o cierra sesión: que no se pierda nada
            return 1
        if msg == WM_ENDSESSION:
            if wparam:
                mostrar_todas()
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            quitar_bandeja()
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.PostQuitMessage(0)
            return 0
    except Exception:
        pass
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def crear_ventana_oculta():
    global MSG_TASKBAR_CREATED
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.lpfnWndProc = proc_ventana
    wc.hInstance = hinst
    wc.lpszClassName = CLASE_OCULTA
    user32.RegisterClassW(ctypes.byref(wc))
    # Ventana normal (no "message-only") y sin mostrar: así recibe los avisos de suspensión
    hwnd = user32.CreateWindowExW(0, CLASE_OCULTA, "Koperfield", 0, 0, 0, 0, 0,
                                  None, None, hinst, None)
    MSG_TASKBAR_CREATED = user32.RegisterWindowMessageW("TaskbarCreated")
    if hwnd:
        wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
    return hwnd


def main():
    global hwnd_oculta, hicono, ultimo_tic
    if ya_esta_abierta():
        return  # ya hay otra copia funcionando: esta se cierra sin hacer nada
    cargar_al_arrancar()
    recuperar_escondidas_anteriores()
    atexit.register(mostrar_todas)  # así nunca se pierden ventanas al salir

    hwnd_oculta = crear_ventana_oculta()
    if not hwnd_oculta:
        return
    hicono = cargar_icono()

    listo = threading.Event()
    hilo = threading.Thread(target=bucle_hook, args=(listo,), daemon=True)
    hilo.start()
    listo.wait(5)
    if not hook_actual:
        user32.DestroyWindow(hwnd_oculta)
        return

    # Cada 2 segundos: mira si cambió la configuración y si venimos de una suspensión
    ultimo_tic = time.time()
    user32.SetTimer(hwnd_oculta, 1, 2000, None)
    actualizar_bandeja(forzar_alta=True)

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    mostrar_todas()
    if hilo_hook_id:
        user32.PostThreadMessageW(hilo_hook_id, WM_QUIT, 0, 0)
    hilo.join(2)


if __name__ == "__main__":
    main()
