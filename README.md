# Telegram-Forwarder

Bot en Python para copiar mensajes con archivos desde uno o varios canales/grupos de Telegram hacia otros destinos, con filtros por tipo, duracion minima de video y palabras clave.

El flujo de ejecucion es interactivo: al iniciar te guia paso a paso para elegir canales, tipos de archivo y filtros.

## Caracteristicas principales

- Reenvio entre canales/grupos de Telegram (1 o multiples pares origen -> destino).
- Soporte de tipos: `video`, `photo`, `audio`, `document`, `voice`, `gif`, `sticker`.
- Filtro por temas/palabras clave en texto o caption.
- Filtro de duracion minima para videos.
- Deteccion de duplicados en destino (opcional).
- Reintentos automaticos con backoff exponencial.
- Manejo de `FloodWait` (rate limit de Telegram).
- Dead Letter Queue en `failed_videos.json` para mensajes que fallan despues de reintentos.
- Persistencia de progreso para reanudar donde quedo (`channel_states.json` por defecto).
- Notificaciones opcionales de finalizacion/error a un chat de Telegram.
- Barra de progreso con `tqdm`.

## Arquitectura

El proyecto sigue *screaming architecture*: las carpetas se nombran por lo que hace el bot, no por la tecnologia que usa. Los detalles tecnicos (Telethon, `.env`, logging) quedan aparte, en `infraestructura/`.

```text
main.py                      # punto de entrada (uv run main.py)
reenviador/
├── reenvio/                 # caso de uso principal: copiar archivos entre canales
│   ├── modelo.py            #   PedidoDeReenvio, ParPorCopiar y Estadisticas
│   ├── reenviar_archivos.py #   orquesta cada par origen -> destino
│   ├── enviador.py          #   envio con reintentos, FloodWait y caption largo
│   ├── reintentos.py        #   backoff exponencial
│   └── caption.py           #   truncado seguro del caption
├── seleccion/               # que mensajes se copian
│   ├── tipos_de_medio.py    #   clasificacion video/foto/gif/sticker/...
│   ├── filtros.py           #   duracion, palabras clave y SelectorDeMensajes
│   └── duplicados.py        #   medios que ya existen en destino
├── progreso/                # reanudar donde quedo
│   ├── repositorio_estado.py
│   └── progreso_contiguo.py #   que ID es seguro guardar con envios concurrentes
├── fallidos/                # mensajes que no se pudieron enviar
│   ├── cola_fallidos.py     #   Dead Letter Queue (failed_videos.json)
│   └── recuperacion.py      #   reintento al inicio de la siguiente corrida
├── sesion/                  # recordar el inicio de sesion entre corridas
│   ├── sesion_guardada.py   #   archivo .session (incluye el API ID/hash mientras hay sesion)
│   └── datos_locales.py     #   progreso, fallidos y log: se borran al cerrar sesion
├── chats/                   # canales, grupos y temas de la cuenta
│   └── catalogo.py          #   se carga al iniciar sesion; el asistente elige de esta lista
├── notificaciones/          # avisos de fin de corrida y errores
├── asistente/               # asistente interactivo de consola
│   ├── consola.py           #   flujo completo: sesion -> lista -> pedido -> reenvio -> resultado
│   ├── inicio_sesion.py     #   credenciales, telefono y codigo, sesion guardada, cerrar sesion
│   ├── eleccion_chats.py    #   elegir canales y temas de la lista (o por ID)
│   ├── pedido.py            #   palabras clave, tipos de archivo, duracion y resumen
│   ├── resultado.py         #   confirmacion antes de enviar y resultado final
│   └── ui.py                #   titulos, mensajes y preguntas de la consola
└── infraestructura/         # detalles tecnicos
    ├── cliente_telegram.py  #   wrapper de Telethon
    ├── configuracion.py     #   variables de entorno
    └── logs.py              #   logging a consola y archivo
```

`infraestructura/` no importa nada de las funcionalidades y no hay imports circulares. `reenvio/reenviar_archivos.py` es el que orquesta todas las piezas.

## Requisitos

- Python `>= 3.13`
- Cuenta de Telegram y acceso a los canales/grupos de origen y destino.
- Credenciales API de Telegram (API ID y API hash):
  - Se obtienen en [my.telegram.org](https://my.telegram.org), en *API development tools*.
  - Se ingresan por consola solo la primera vez: quedan guardadas dentro de la sesion y se borran al cerrar sesion. Nunca se leen del `.env`.
- `uv` instalado.

## Instalacion con uv

En PowerShell (dentro del proyecto):

```powershell
uv sync
```

Esto instala lo definido en `pyproject.toml`:

- `telethon`
- `python-dotenv`
- `tqdm`

Opcional para mejorar rendimiento criptografico en Telethon:

```powershell
uv add cryptg
```

## Configuracion

El `.env` es **opcional** y nunca lleva credenciales: sin el, el asistente pide todo por consola (credenciales, inicio de sesion y canales). Sirve solo para no reescribir canales y filtros en cada corrida.

1. Si lo quieres, crea tu archivo `.env`:

```powershell
Copy-Item .env.example .env
```

2. Edita `.env` con tus valores.

### Variables de entorno

| Variable | Requerida | Default | Descripcion |
|---|---|---|---|
| `TELEGRAM_SESSION_NAME` | No | `mi_sesion_telegram` | Nombre del archivo de la sesion guardada (`<nombre>.session`). |
| `CHANNEL_ORIGEN_ID` | Condicional | `None` | Canal/grupo de origen (ej. `-1001234567890` o `@usuario`). |
| `CHANNEL_DESTINO_ID` | Condicional | `None` | Canal/grupo destino (ej. `-1009876543210` o `@usuario`). |
| `CHANNEL_MAPPINGS` | Condicional | `""` | Lista JSON con pares `origen`/`destino`. Tiene prioridad sobre `CHANNEL_ORIGEN_ID` y `CHANNEL_DESTINO_ID`. |
| `MIN_DURACION_VIDEO_MINUTOS` | No | `5` | Duracion minima para videos (env usa entero). |
| `EVITAR_DUPLICADOS` | No | `True` | Si es `True`, analiza destino para no reenviar medios repetidos. |
| `DELAY_ENTRE_MENSAJES` | No | `1.5` | Espera entre envios cuando concurrencia = `1`. |
| `MAX_RETRIES` | No | `3` | Numero maximo de reintentos por mensaje fallido. |
| `RETRY_BASE_DELAY` | No | `1.0` | Delay base para backoff exponencial (1s, 2s, 4s, ...). |
| `MAX_CONCURRENT_VIDEOS` | No | `1` | Nivel de concurrencia minima `1`. |
| `ARCHIVO_ESTADO` | No | `channel_states.json` | Archivo JSON de progreso por par origen-destino. |
| `ENABLE_NOTIFICATIONS` | No | `False` | Activa envio de resumen y errores a Telegram. |
| `NOTIFICATION_CHAT_ID` | Condicional | `None` | Chat ID numerico para notificaciones (si `ENABLE_NOTIFICATIONS=True`). |

Notas importantes:

- "Condicional" significa: debes configurar canales en `.env` solo si en la ejecucion eliges usar canales desde `.env`.
- Si `CHANNEL_MAPPINGS` esta presente y es valido, se usa ese valor antes que el par simple origen/destino.
- `NOTIFICATION_CHAT_ID` debe ser numerico para activarse correctamente.

Ejemplo de `CHANNEL_MAPPINGS`:

```env
CHANNEL_MAPPINGS=[{"origen":"-1001111111111","destino":"-1002222222222"},{"origen":"@canal_a","destino":"@canal_b"}]
```

## Ejecucion

```powershell
uv run main.py
```

Al iniciar:

1. **Sesion de Telegram**:
   - **Primera vez** (no hay sesion guardada): pide el **API ID**, el **API hash**, tu telefono, el codigo que te envia Telegram y, si tu cuenta la tiene, la contrasena de verificacion en dos pasos. Luego guarda la sesion junto con el API ID y el hash.
   - **Siguientes veces**: no pide ningun dato. Muestra la cuenta guardada y te deja elegir:
     - `1) Continuar con esta cuenta` (`Enter`).
     - `2) Cerrar sesion`: tras confirmar, la cierra en Telegram y **deja el proyecto limpio** (borra la sesion con tu API ID y hash, el progreso, los mensajes fallidos y el log). Luego pregunta si quieres entrar con otra cuenta.
   - Si Telegram rechaza el API ID o el hash, los vuelve a pedir (sin borrar la sesion).
   - El API hash y la contrasena se escriben ocultos. Si la terminal no lo permite (Git Bash o la ventana *Run* de algunos IDE), se escriben visibles y el asistente lo avisa.
   - Si la sesion guardada ya no es valida (por ejemplo, la cerraste desde el celular), la borra y pide iniciar sesion de nuevo.
   - Mientras no inicies sesion, el bot no crea ningun archivo: el log y el progreso aparecen recien con la sesion iniciada.
2. **Carga tus canales, grupos y temas**: con la sesion iniciada, lee todos los canales y grupos de tu cuenta y, en los grupos tipo foro, sus temas.
3. Si hay canales en el `.env`, te pregunta si quieres usarlos; si no, eliges origen y destino **de la lista** (ver [Elegir canales y temas](#elegir-canales-y-temas)).
4. Te permite configurar:
   - palabras clave,
   - tipos de archivo,
   - duracion minima de video.
5. Muestra un resumen (con los nombres de los canales y temas) y pide confirmacion.
6. **Antes de enviar**, por cada par origen -> destino muestra cuantos archivos va a copiar (y cuantos son reintentos de fallidos o se omitieron por filtros) y pregunta `Copiar N archivos ahora [S/n]`. Si respondes `n`, ese par no se envia y el progreso no avanza: la proxima corrida te los vuelve a ofrecer.
7. Mientras copia, la barra de progreso se mantiene en su linea aunque aparezcan avisos (por ejemplo, esperas por limite de Telegram).
8. **Al terminar** (o si cortas con `Ctrl+C`) muestra el resultado: copiados, omitidos, fallidos, pares con errores y el tiempo total.

## Elegir canales y temas

El asistente muestra tus canales y grupos numerados, en el mismo orden que la app de Telegram:

```text
    1) Peliculas HD  [canal]  -1001234567890
    2) Series  [foro, 12 temas]  -1009876543210
    3) Charla  [grupo]  -1002222222222
  › Origen: numero, texto para buscar o ID/@usuario [*=ver todos]:
```

- **Numero**: elige ese canal o grupo.
- **Texto**: filtra la lista por nombre, sin importar mayusculas ni tildes (`peliculas` encuentra `Películas`). `*` vuelve a mostrar todos.
- **ID o @usuario**: sigue funcionando como antes: `-1001234567890`, `@mi_canal` o `-1001234567890,123` (canal y tema).
- Si hay muchos, se muestran los primeros 30; usa la busqueda para llegar al resto.

Si eliges un **foro**, luego eliges el tema de su lista:

- En el **origen**, `0` (o `Enter`) copia de **todo el grupo** (todos los temas).
- En el **destino**, `0` (o `Enter`) publica en el tema **General**.
- Los temas cerrados aparecen marcados como `(cerrado)`.

La lista marca con `⚠` los chats que no van a funcionar en ese rol, y si eliges uno pregunta si usarlo igual:

- En el **origen**, `⚠ protegido`: el chat tiene el contenido protegido y Telegram no deja copiar sus archivos.
- En el **destino**, `⚠ sin permiso para publicar`: canales donde no eres administrador con permiso de publicar, o grupos que prohiben enviar archivos. Solo se marca cuando es seguro que fallara.

Si la lista no se pudo cargar (por ejemplo, sin conexion), el asistente vuelve a pedir los IDs a mano.

## Filtros y logica de reenvio

- Tipos de archivo:
  - Por defecto, si no eliges nada, usa solo `video`.
- Duracion minima:
  - Solo aplica cuando `video` esta en los tipos seleccionados.
- Palabras clave (no confundir con los temas de un foro):
  - Compara en minusculas contra `mensaje.text` (texto/caption).
  - Si no hay palabras clave, no filtra por texto.
- Duplicados:
  - Si `EVITAR_DUPLICADOS=True`, analiza el destino y evita reenviar medios ya vistos.
  - Tambien evita duplicados dentro de la misma corrida.

## Estado, logs y archivos generados

| Archivo | Para que sirve |
|---|---|
| `bot_telegram.log` | Log general de ejecucion (INFO/WARNING/ERROR). |
| `channel_states.json` | Ultimo mensaje procesado por par `origen->destino` (reanudar corrida). |
| `failed_videos.json` | DLQ de mensajes que fallaron tras todos los reintentos. |
| `<TELEGRAM_SESSION_NAME>.session` | Sesion guardada de Telegram, con tu API ID y hash. **Da acceso total a tu cuenta**: no la compartas ni la subas a git. |

Ninguno de estos archivos existe hasta que inicias sesion, y `Cerrar sesion` los borra todos. El API ID y el API hash no tienen archivo propio: se guardan dentro del `.session` y desaparecen con el.

## Reanudar procesamiento

El bot guarda por cada par origen-destino el ultimo `message_id` procesado (todos los anteriores ya terminaron).

- Si interrumpes el proceso (`Ctrl+C`) y vuelves a correr, continuara desde el ultimo ID guardado.
- El guardado es incremental durante la corrida y tambien se hace al interrumpir o terminar.
- Los mensajes que fallaron quedan en `failed_videos.json` y se reintentan automaticamente al inicio de la siguiente corrida. Si ya no existen en origen (o ya estan en destino con `EVITAR_DUPLICADOS=True`), se quitan de la lista.

## Ejecucion con multiples pares (mappings)

Opciones:

- Par unico: `CHANNEL_ORIGEN_ID` + `CHANNEL_DESTINO_ID`.
- Multiples pares: `CHANNEL_MAPPINGS` como JSON.

Limitacion actual sobre topics:

- Si procesas multiples pares en una sola corrida, los `topic_id` interactivos no se aplican a cada par (solo aplican cuando hay un par unico).

## Notificaciones opcionales

Si activas:

```env
ENABLE_NOTIFICATIONS=True
NOTIFICATION_CHAT_ID=-1001234567890
```

El bot puede enviar:

- resumen de finalizacion (copiados/omitidos/fallidos),
- alerta de error critico.

## Pruebas

El proyecto incluye pruebas unitarias basicas:

```powershell
uv run python -m unittest discover -s tests -v
```

## Troubleshooting

### `Telegram rechazo el API ID / API hash`

- Copialos de nuevo desde [my.telegram.org](https://my.telegram.org) (*API development tools*).
- Si ya tenias una sesion guardada, no se borra: solo vuelve a pedir el API ID y el hash.

### `A wait of N seconds is required` al iniciar sesion

- Si cierras sesion y vuelves a entrar muchas veces seguidas, Telegram limita el envio de codigos. Espera el tiempo indicado antes de volver a intentar.

### Error: no hay canales configurados

- Define `CHANNEL_ORIGEN_ID` y `CHANNEL_DESTINO_ID`, o un `CHANNEL_MAPPINGS` valido.
- O en el asistente selecciona ingreso manual de canales.

### No reenvia mensajes

- Revisa filtros activos:
  - tipo de archivo,
  - duracion minima,
  - temas,
  - deduplicacion.
- Revisa si el estado ya avanzo (`channel_states.json`).

### `FloodWaitError` / limite de Telegram

- Es normal en cuentas con mucho trafico.
- Reduce concurrencia (`MAX_CONCURRENT_VIDEOS=1`) y/o sube `DELAY_ENTRE_MENSAJES`.

### Mensajes fallidos por caption largo

- El bot intenta truncar caption automaticamente.
- Si aun falla, revisa detalle en `failed_videos.json`.

### Duplicados tarda mucho

- La deduplicacion recorre historial de destino; en canales grandes puede tardar.
- Si prefieres velocidad, prueba `EVITAR_DUPLICADOS=False`.

## Buenas practicas

- Empieza con un canal de prueba antes de usar produccion.
- Manten `MAX_CONCURRENT_VIDEOS` bajo para evitar limites.
- Haz respaldo de `channel_states.json` si el progreso es critico.
- Revisa periodicamente `failed_videos.json`.
