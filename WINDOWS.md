# Probar Miga en Windows

Miga está preparado para Windows 11 x64 y Windows 10 x64 desde la versión 1809 con una versión de Qt compatible. Las pruebas automáticas utilizan Windows Server x64. La valoración visual, los dispositivos físicos y los cambios de monitor o de sesión requieren un escritorio cliente. [Ejecuciones de las pruebas nativas](https://github.com/camilo477/desktop-pet/actions/workflows/windows.yml).

## Descargar la aplicación

1. Abre [Releases](https://github.com/camilo477/desktop-pet/releases) y descarga **Miga-Windows-x64.zip** en Assets / Recursos.
2. Clic derecho en el ZIP → **Extraer todo**. Conserva la carpeta completa `Miga`, incluida `_internal`.
3. Abre **Miga.exe** con doble clic. Puedes crear un acceso directo en el escritorio.

El paquete incluye Python y sus dependencias; no necesitas instalar herramientas ni usar comandos. Para cerrar, clic derecho sobre Miga → **Salir**. Para actualizar, ciérrala y reemplaza la carpeta completa con la nueva versión. Para desinstalar, ciérrala y elimina la carpeta y tus accesos directos. Tus preferencias permanecen guardadas.

## Instalar desde el código

1. Instala Python 3.12 de 64 bits con su lanzador para Windows. [Descargas oficiales de Python](https://www.python.org/downloads/windows/).
2. Descarga el [ZIP de la rama main](https://github.com/camilo477/desktop-pet/archive/refs/heads/main.zip), extrae todos los archivos y conserva la carpeta en una ubicación de tu usuario. También puedes actualizar una copia Git existente.
3. Abre PowerShell en la carpeta que contiene `install.ps1` y ejecuta:

   ```powershell
   py -3 .\windows\setup.py install
   ```

También puedes ejecutar `.\install.ps1` si tu equipo permite scripts de PowerShell. Ambos métodos usan el mismo instalador. Las dependencias se descargan durante la instalación. Después, Miga funciona sin conexión. La instalación registra únicamente el acceso directo en Inicio y la carpeta del comando en el PATH de tu usuario.

## Iniciar, cerrar y actualizar

Abre **Miga Desktop Pet** desde Inicio. También puedes abrir una **nueva** ventana de PowerShell o CMD en cualquier directorio y ejecutar:

```powershell
miga
miga off
```

El segundo comando guarda las preferencias y cierra Miga. También puedes hacer clic derecho sobre el gato y elegir **Salir**. Si la terminal aún usa el PATH anterior, abre una nueva desde Inicio o ejecuta `& '.\windows\bin\miga.cmd'` desde el proyecto.

Para actualizar, cierra Miga, actualiza los archivos de la misma carpeta y repite la instalación. Para desinstalar, ejecuta `py -3 .\windows\setup.py uninstall` desde esa carpeta antes de quitar el código fuente. También está disponible `.\uninstall.ps1`. Se conservan tus preferencias de QSettings.

## Prueba en tu escritorio

| Acción | Qué observar |
| --- | --- |
| Inicia Miga desde Inicio y dos veces desde terminales distintas. Cierra las terminales. | Queda un solo gato, sin consola persistente. |
| Escribe texto de prueba en el Bloc de notas. Acaricia la cabeza, toca orejas y cola y arrastra a Miga. | La aplicación conserva el foco al interactuar con el gato. Tras soltarlo vuelve a escribir desde la primera pulsación. |
| Superpón una esquina vacía de Miga a un control. Prueba el clic, el menú y **Siempre visible**. | El control de debajo recibe el clic en el área vacía. El gato recibe los clics en su silueta. Repite con pausa, otro pelaje y otro formato. |
| Mantén una tecla diez segundos y usa ambos Shift/Ctrl, AltGr, los dos Enter, Num Lock, flechas, Pause y Print Screen. Mueve el ratón y usa ambas ruedas disponibles. | Se iluminan las posiciones físicas visibles. Al soltar se apagan. Las teclas ausentes en el formato compacto cuentan como actividad sin contacto ficticio. Los atajos reservados pueden activar funciones de Windows. |
| Cambia la distribución con el selector de Windows, incluso con una tecla mantenida. Prueba la selección manual y cambia de aplicación. | **Teclado → Distribución → Automática** identifica el mapa compatible del hilo en primer plano. Una variante personalizada puede requerir selección manual. |
| Déjalo tres minutos sin actividad. Despiértalo, pausa y reanuda las animaciones. Bloquea y desbloquea la sesión, y prueba suspender y reanudar. | Duerme sentado y vuelve a responder sin teclas atascadas. |
| Mueve Miga entre pantallas, prueba 100, 125, 150, 175 y 200 %, y desconecta la pantalla secundaria. | Se conserva el tamaño lógico. Revisa los bordes, las caricias, el arrastre y la recuperación en el área visible. |
| Cambia tamaño, pelaje y teclado. Cierra con el menú y con `miga off`, y repite la instalación. | Se conservan las preferencias. |

El escritorio seguro, UAC y la pantalla completa exclusiva pueden limitar las entradas o la visibilidad. Miga respeta esas restricciones. Si encuentras un fallo, indica la versión de Windows, escala, configuración de Miga, pasos y resultado observado. Para ver un error de inicio en la terminal, cierra Miga y ejecuta `& '.\.venv-win\Scripts\python.exe' .\main.py --run`. Comparte solo el mensaje de error, sin texto escrito, rutas personales ni capturas del escritorio.

## Carpeta portable de prueba

En Windows x64, después de instalar el proyecto, ejecuta `.\windows\build.ps1`. El script crea un entorno temporal de construcción con PyInstaller. Conserva junta la carpeta completa `dist\Miga`, incluidos sus plugins de Qt y recursos SVG. Puedes iniciar `Miga.exe` con doble clic y cerrar con `& '.\dist\Miga\Miga.exe' off`. El equipo de destino puede ejecutar esa carpeta sin instalar Python. Es una compilación de prueba sin firma. Windows puede mostrar un aviso de reputación. [Modo de distribución en carpeta de PyInstaller](https://pyinstaller.org/en/stable/usage.html).
