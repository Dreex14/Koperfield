<p align="center">
  <img src="recursos/koperfield.png" width="128" alt="Koperfield icon">
  &nbsp;&nbsp;&nbsp;
  <img src="recursos/koperfield_opciones.png" width="128" alt="Koperfield Options icon">
</p>
<p align="center">
  <sub><b>Koperfield</b> &nbsp;·&nbsp; <b>Koperfield Options</b></sub>
</p>

<h1 align="center">Koperfield</h1>

<p align="center">Hide windows instantly on Windows with a keyboard shortcut, and bring them back just as fast.</p>

<p align="center"><sub>🇪🇸 ¿Prefieres español? Despliega <b>«Leer en español»</b> al final de esta página.</sub></p>

---

## Features

- **Two modes**
  - **Selective:** hides every window of the programs you choose (browsers, WhatsApp, Discord…) at once.
  - **Classic:** hides only the active window, one at most.
- **Customisable shortcuts** (the same for both modes):

  | Action | Default shortcut |
  |---|---|
  | Hide | `Ctrl` + `Space` |
  | Show | `AltGr` + `Space` |
  | Pause / resume | `Ctrl` + `Shift` + `Space` |
  | Quit (and show everything) | `Ctrl` + `Left Alt` + `Q` |

- **Hidden windows disappear from the taskbar** and come back in their previous state and stacking order.
- **Survives sleep, hibernation and lock screen.** The keyboard hook is reinstalled automatically when the PC wakes up or the session is unlocked.
- **Never loses a window:** hidden windows are shown again when you quit, when Windows shuts down, and on the next start if the program was closed abruptly.
- **Optional tray icon** with "Show hidden windows", pause, mode switch and options.
- **Spanish or English** interface: Spanish if your keyboard or Windows is in Spanish (Spain or Latin America), English otherwise.

## Privacy and safety

- **100 % local.** No telemetry, no network connections, no updates, no accounts.
- It only writes two files, next to the program: `koperfield_config.json` (your settings) and `koperfield_escondidas.json` (the list of hidden windows, deleted when they are shown again).
- It does **not** inject code into other programs, read their memory or open handles to their processes. Program names are read from a snapshot of the Windows process list, so games and anti-cheat systems are left alone.
- Only Python's standard library is used (`ctypes`, `tkinter`, `json`…).

## Download and use

1. Download `Koperfield-v1.0-windows.zip` from [Releases](../../releases/latest) and extract it. Keep `Koperfield.exe` and `Koperfield Options.exe` together in the same folder.
2. Run `Koperfield.exe`. It stays in the background (and in the tray, if enabled).
3. Run `Koperfield Options.exe` to choose the mode, shortcuts and programs. Changes apply in a couple of seconds without restarting.

To start it with Windows, put a shortcut to `Koperfield.exe` in the Startup folder (`Win` + `R` → `shell:startup`).

> Windows SmartScreen or some antivirus programs may warn about unsigned executables built with PyInstaller. You can always run it from source instead.

## Run from source

Requires [Python 3](https://www.python.org/) on Windows. No extra packages are needed.

```bash
pythonw koperfield.pyw
pythonw koperfield_opciones.pyw
```

## Build

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name Koperfield --icon recursos/koperfield.ico koperfield.pyw
pyinstaller --onefile --noconsole --name "Koperfield Options" --icon recursos/koperfield_opciones.ico --add-data "recursos/koperfield_opciones.ico;." koperfield_opciones.pyw
```

The icons are generated with `python recursos/crear_icono.py` (requires Pillow).

## Credits

- Inspired by the original **Koperfield** by **Pukerman**, a small utility for hiding windows. This is an independent project written from scratch; it does not contain any of its code or resources.
- Not affiliated with Kopperfield, Inc. or David Copperfield.

### Third-party tools

| Tool | Used for | License |
|---|---|---|
| [Python](https://www.python.org/) | Runtime and standard library | [PSF License](https://docs.python.org/3/license.html) |
| [PyInstaller](https://pyinstaller.org/) | Building the `.exe` files | [GPL 2.0 with bootloader exception](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) (does not affect this project's license) |
| [Pillow](https://python-pillow.org/) | Generating the icons (`crear_icono.py` only) | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |

## License

[MIT](LICENSE) © 2026 Dreex

Made by **Dreex**.

---

<details>
<summary><b>🇪🇸 Leer en español</b></summary>

<br>

**Koperfield** esconde al instante ventanas de Windows con un atajo de teclado y las vuelve a mostrar igual de rápido.

### Funciones

- **Dos modos**
  - **Selectivo:** esconde de golpe todas las ventanas de los programas que elijas (navegadores, WhatsApp, Discord…).
  - **Clásico:** esconde solo la ventana activa, como máximo una.
- **Atajos personalizables** (los mismos en los dos modos):

  | Acción | Atajo por defecto |
  |---|---|
  | Esconder | `Ctrl` + `Espacio` |
  | Mostrar | `AltGr` + `Espacio` |
  | Pausar / reanudar | `Ctrl` + `Shift` + `Espacio` |
  | Salir (y mostrar todo) | `Ctrl` + `Alt izquierdo` + `Q` |

- **Las ventanas escondidas desaparecen de la barra de tareas** y vuelven en su estado y orden anteriores.
- **Aguanta la suspensión, la hibernación y la pantalla de bloqueo.** El detector de teclado se reinstala solo al despertar el PC o al desbloquear la sesión.
- **Nunca pierde una ventana:** las escondidas se muestran al salir, al apagar Windows y, si el programa se cerró de golpe, al volver a abrirlo.
- **Icono en la bandeja opcional** con "Mostrar escondidas", pausa, cambio de modo y opciones.
- **Interfaz en español o en inglés:** en español si tu teclado o tu Windows están en español (de España o latinoamericano); si no, en inglés.

### Privacidad y seguridad

- **100 % local.** Sin telemetría, sin conexiones a internet, sin actualizaciones y sin cuentas.
- Solo escribe dos archivos, junto al programa: `koperfield_config.json` (tus ajustes) y `koperfield_escondidas.json` (la lista de ventanas escondidas, que se borra al mostrarlas).
- **No** inyecta código en otros programas, no lee su memoria ni abre sus procesos. Los nombres de los programas se sacan de una "foto" de la lista de procesos de Windows, así que no molesta a los juegos ni a sus anticheats.
- Solo usa la biblioteca estándar de Python (`ctypes`, `tkinter`, `json`…).

### Descarga y uso

1. Descarga `Koperfield-v1.0-windows.zip` desde [Releases](../../releases/latest) y descomprímelo. Deja `Koperfield.exe` y `Koperfield Options.exe` juntos en la misma carpeta.
2. Abre `Koperfield.exe`. Se queda en segundo plano (y en la bandeja, si está activado).
3. Abre `Koperfield Options.exe` para elegir el modo, los atajos y los programas. Los cambios se aplican en un par de segundos, sin reiniciar.

Para que arranque con Windows, pon un acceso directo a `Koperfield.exe` en la carpeta de Inicio (`Win` + `R` → `shell:startup`).

> Windows SmartScreen o algún antivirus pueden avisar de los ejecutables sin firmar hechos con PyInstaller. Siempre puedes usarlo desde el código fuente.

### Usarlo desde el código fuente

Necesitas [Python 3](https://www.python.org/) en Windows, sin paquetes adicionales:

```bash
pythonw koperfield.pyw
pythonw koperfield_opciones.pyw
```

Las instrucciones para compilar están en la sección *Build* de arriba.

### Créditos

- Inspirado en el **Koperfield** original de **Pukerman**, una pequeña utilidad para esconder ventanas. Este es un proyecto independiente escrito desde cero; no contiene nada de su código ni de sus recursos.
- Sin relación con Kopperfield, Inc. ni con David Copperfield.
- Herramientas de terceros: Python (PSF License), PyInstaller (GPL 2.0 con excepción del bootloader, no afecta a la licencia de este proyecto) y Pillow (MIT-CMU, solo para generar los iconos).

### Licencia

[MIT](LICENSE) © 2026 Dreex

Hecho por **Dreex**.

</details>
