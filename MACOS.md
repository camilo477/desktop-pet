# Miga en macOS

Miga utiliza el mismo gato, pelajes, teclados y animaciones que las versiones de Linux y Windows. Los paquetes de desarrollo son nativos para **Apple Silicon (arm64)** o **Intel (x86_64)**. El mínimo del proyecto es **macOS Sequoia 15**. Los binarios de PySide6/Shiboken 6.11 utilizados declaran ese destino. Las pruebas automáticas se ejecutan en macOS 15. [Requisitos de Qt para macOS](https://doc.qt.io/qt-6.11/macos.html) · [Pruebas por arquitectura](https://github.com/camilo477/desktop-pet/actions/workflows/macos.yml).

## Instalar desde el código

1. Descarga el [código de main](https://github.com/camilo477/desktop-pet/archive/refs/heads/main.zip) y descomprime el ZIP. Para compilar necesitas Python nativo 3.11 o posterior con ruedas compatibles (se probó 3.12) y las herramientas de línea de comandos de Apple. Puedes obtener Python en [python.org](https://www.python.org/downloads/macos/).
2. Abre Terminal en la carpeta que contiene `README.md` y ejecuta el instalador.

   ```sh
   ./macos/install.sh
   ```

   Si tienes varias versiones de Python, puedes elegir una con `MIGA_PYTHON="/ruta/a/python3.12" ./macos/install.sh`. En Apple Silicon utiliza el Python ARM64.
3. Abre **Miga** desde tu carpeta personal **Aplicaciones** en Finder. Si la shell no encuentra `miga`, añade esta línea a tu configuración personal de Zsh u otra shell.

   ```sh
   export PATH="$HOME/.local/bin:$PATH"
   ```

El instalador compila en un entorno virtual temporal, instala `~/Applications/Miga.app` y crea `~/.local/bin/miga`. Solo la instalación y la construcción descargan dependencias. Para actualizar, repite la instalación y abre Miga de nuevo. Se conservan tus preferencias.

## Abrir, cerrar y desinstalar

```sh
miga
miga off
```

Puedes cerrar la terminal después de iniciar Miga. Finder y el comando comparten instancia y preferencias. También puedes hacer clic derecho en Miga y elegir **Salir**.

Para quitar la instalación de tu usuario, ejecuta `./macos/uninstall.sh` desde el proyecto. Si copiaste la aplicación por tu cuenta, ciérrala y elimina esa copia desde Finder. Tus preferencias permanecen guardadas. Puedes retirar el permiso de entrada en Ajustes del Sistema.

## Permisos y modo local

Miga arranca sin pedir acceso global. Con el permiso desactivado siguen funcionando las animaciones, el sueño, los menús, las caricias y el arrastre. El tiempo de inactividad cuenta desde la última actividad que Miga pudo observar.

Puedes habilitar las reacciones mientras trabajas en otra aplicación desde el menú de Miga.

1. Haz clic derecho en el gato y abre **Entrada global en macOS → Información y permisos…**. El submenú muestra el estado actual.
2. Elige **Solicitar permiso**. En **Ajustes del Sistema → Privacidad y seguridad → Monitorización de entrada**, habilita la copia de Miga que instalaste. Si macOS pide cerrar y volver a abrir la aplicación, hazlo.
3. Para dejar de observar la entrada, desmarca **Reaccionar a actividad**, pausa las animaciones o retira el permiso en esos mismos ajustes.

El observador de Quartz es de solo escucha. Miga utiliza la posición física de la tecla, su estado, el movimiento del puntero y la rueda. No reconstruye texto ni conserva un historial. El sistema protege la entrada segura. La aplicación solo solicita Monitorización de entrada. [Control de la monitorización de entrada en macOS](https://support.apple.com/guide/mac-help/control-access-to-input-monitoring-on-mac-mchl4cedafb6/mac).

## Construir o usar un paquete

Ejecuta `./macos/build.sh` en un Mac de la arquitectura deseada. Obtendrás `dist/arm64/Miga.app` o `dist/x86_64/Miga.app`. El paquete incluye Python, Qt, los plugins, Cocoa, Quartz y los recursos de Miga. Un Python local compilado para un macOS más reciente puede elevar el mínimo del paquete. La compilación registra ese mínimo en `LSMinimumSystemVersion`.

En un Mac compatible puedes copiar el paquete completo a tu carpeta Aplicaciones y abrirlo desde Finder sin instalar Python. Si también quieres el comando de terminal, usa el instalador desde una copia del proyecto.

```sh
./macos/install.sh --app "dist/$(uname -m)/Miga.app"
```

El identificador estable del paquete es `io.github.camilo477.miga`. Estas compilaciones de desarrollo llevan firma **ad hoc**. La distribución con Developer ID y la notarización están pendientes. Gatekeeper puede rechazar una copia descargada y macOS puede volver a pedir permiso tras una actualización. Para probar el proyecto en ese caso, compílalo localmente desde el código de confianza.

## Validación pendiente en un Mac de uso diario

En los runners ARM64 e Intel se abrió el paquete con LaunchServices, se comprobó la instancia única y se verificaron el panel sin foco y los destinos de clic de una zona visible y una transparente. Con el permiso ya disponible, una pulsación sintética llegó al observador de Quartz y a la ventana de prueba en primer plano. La denegación y la revocación se comprobaron simulando la respuesta de la consulta de permiso.

| Prueba | Qué comprobar |
| --- | --- |
| Finder y Terminal | Abre Miga desde ambos, cierra Terminal y ejecuta `miga off`. Debe quedar un solo gato y cerrar ordenadamente. |
| Permisos | Empieza sin permiso. Acaricia cabeza, orejas y cola. Concede el permiso desde el menú y luego retíralo. Debe quedar disponible el modo local y desaparecer cualquier tecla mantenida. |
| Escritura y foco | En TextEdit, usa ambos Shift, Control, Option y Command, mantén una tecla y cambia de fuente de entrada. Comprueba foco, etiquetas y patitas. Prueba una fuente desconocida y la selección manual. |
| Ratón y trackpad | Comprueba movimiento, clic y scroll en ambos ejes. Arrastra y suelta al gato, luego escribe y desplázate inmediatamente. |
| Ventana y aspecto | Coloca una esquina transparente encima de un control de otra aplicación. Comprueba los clics, el menú, los tres tamaños, pelajes y formatos de teclado. |
| Sueño y sesión | Tras tres minutos de inactividad observada, comprueba el sueño sentado y el despertar. Bloquea y desbloquea el Mac, suspende y reanuda. |
| Escritorio | Prueba Retina, dos monitores de distinta escala, retirada del secundario, Spaces, Mission Control, pantalla completa y Stage Manager. Comprueba nivel de ventana, Dock y selector de aplicaciones. |
| Actualización y retirada | Cambia tamaño, teclado y pelaje. Cierra, reinstala y abre desde Finder y Terminal. Verifica las preferencias y desinstala. |

Los formatos ANSI/ISO conservan la geometría compartida. Los símbolos de Command, Option y Control se adaptan a macOS. Una fuente personalizada o un método de entrada no identificado utiliza el respaldo estadounidense indicado en el menú. Los atajos de firmware, Globe y los controles multimedia pueden quedar reservados por macOS. La aplicación usa niveles de ventana normales o flotantes y deja la gestión de Spaces y pantalla completa al sistema.
