Descripción general

La aplicación es una app Streamlit para explorar la estructura hardware de un simulador a partir de carpetas reales del sistema de ficheros. No parte de un Excel o CSV como origen principal: el usuario introduce una ruta raíz, la app recorre el árbol de directorios, detecta carpetas con códigos HW tipo A01, A0101, A010101, normaliza esos códigos y construye una jerarquía lógica de PBS/HW.

La arquitectura está bastante bien separada: hay un fichero mínimo de entrada, un orquestador principal, un módulo de escaneo/normalización, un módulo común de UI, una pestaña principal HW PBS, una pestaña LMs ya funcional y varias pestañas futuras todavía pendientes.

Flujo principal de ejecución

El flujo actual es:

Se ejecuta HW_app.py.
HW_app.py importa y ejecuta run_app() desde HW_app_core.py.
HW_app_core.py configura la página Streamlit, aplica el tema visual, pide la ruta raíz en el sidebar, valida que exista y recoge los filtros globales.
Se escanea el directorio con scan_hw_folders().
Se añaden al DataFrame los elementos principales definidos en main_hw_elements.json que no se hayan encontrado físicamente.
Se inicializa la selección global del elemento HW.
Se pinta el sidebar con los elementos principales.
Se renderizan las pestañas principales: HW PBS, LMs, BOM, Material Status y Secuencia de Montaje.
Arquitectura por módulos
HW_app.py

Es el punto de entrada de la aplicación.

No contiene lógica funcional ni visual propia. Su única responsabilidad es importar run_app desde HW_app_core.py y ejecutarlo cuando el fichero se lanza como programa principal.

En la arquitectura, este fichero queda limpio y estable. Sirve únicamente como arranque de Streamlit.

HW_app_core.py

Es el orquestador principal.

Sus responsabilidades son:

Configurar la página Streamlit.
Aplicar el tema visual común con inject_custom_theme().
Gestionar la carga del directorio raíz.
Validar que la ruta exista y sea una carpeta.
Mostrar los controles globales del sidebar:
ruta raíz,
nivel HW máximo,
mostrar u ocultar carpetas vacías,
texto de búsqueda,
botón de actualización de lectura.
Construir el DataFrame base llamando a scan_hw_folders() y add_missing_main_elements().
Inicializar el elemento seleccionado.
Pintar el sidebar global con la estructura principal.
Lanzar las pestañas principales de la app.

La función build_hw_dataframe() centraliza la construcción del DataFrame HW. Primero escanea las carpetas, después añade los elementos principales no encontrados, y finalmente aplica el filtro de carpetas vacías si corresponde.

La selección global se guarda en st.session_state["selected_hw_code"], de modo que todas las pestañas trabajan sobre el mismo elemento HW seleccionado en el sidebar.

HW_scanner.py

Es el núcleo funcional de escaneo y normalización.

Este módulo no pinta la interfaz. Su trabajo es convertir la estructura física de carpetas en una estructura lógica de hardware.

Sus responsabilidades principales son:

Cargar la configuración de elementos principales desde main_hw_elements.json.
Normalizar códigos HW.
Extraer códigos desde nombres de carpeta.
Extraer descripciones desde nombres de carpeta.
Calcular el nivel HW de un código.
Calcular el código padre.
Calcular el código principal.
Recorrer el directorio raíz.
Contar carpetas y ficheros.
Obtener el contenido directo de una carpeta.
Construir el DataFrame base con columnas como:
code,
level,
name,
description,
component,
sica,
path,
parent_code,
main_code,
dirs,
files,
exists.

La regla principal de detección es que una carpeta se reconoce si su nombre empieza por un patrón A seguido de dígitos. Por ejemplo:

A01
A0101
A010101

Además, normalize_code() elimina sufijos 00 cuando el código tiene más de dos dígitos, lo que permite normalizar códigos tipo A0100 a A01.

También contiene funciones de navegación lógica, como:

get_children_by_code()
get_descendant_rows_by_code()
get_main_element_row()
get_sidebar_main_elements()

Estas funciones son importantes porque permiten que la app trabaje por jerarquía lógica de código, no solo por posición física en carpetas.

main_hw_elements.json

Es el catálogo de referencia de los elementos principales del simulador.

Define qué elementos deben aparecer en el sidebar, por ejemplo:

A00 - SIM
A01 - COCKPIT
A02 - AFTERCABIN
A03 - VISUAL DISPLAY SYSTEM
A04 - BASEFRAME
A05 - DRAWBRIDGE
A07 - MOTION SYSTEM
A08 - PROCESSOR RACK #1
A09 - PROCESSOR RACK #2
A12 - UPS
A14 - BREATHING AIR
A15 - AIR CONDITIONING SYSTEM
A18 - FIRE DETECTION
A21 - POWER CABINET
A26 - PLANNER STATION
A27 - DEBRIEFING STATION

Este JSON no es solo decorativo: sirve para saber qué sistemas principales deben existir y para marcar como “no encontrado” cualquier elemento de referencia que no aparezca físicamente en el directorio cargado.

HW_ui_common.py

Es el módulo de UI común y estilo visual compartido.

Sus responsabilidades son:

Inyectar el CSS corporativo con inject_custom_theme().
Aplicar el estilo visual de la app:
fondo azul,
sidebar claro,
botones turquesa,
métricas con fondo corporativo,
tablas oscuras,
tabs y expanders adaptados al estilo.
Renderizar tablas comunes:
render_file_table()
render_level_summary()
Aplicar estilo oscuro a DataFrames mediante style_dark_dataframe().

Este módulo es importante porque evita duplicar estilos en cada pestaña y mantiene la apariencia homogénea.

modules/HW_PBS.py

Es la pestaña principal funcional de estructura HW/PBS.

Es el módulo que muestra la estructura hardware para el elemento seleccionado en el sidebar global.

Sus responsabilidades son:

Mostrar el elemento seleccionado.
Mostrar métricas principales:
código HW,
código SICA,
carpetas,
ficheros,
elementos visibles.
Construir el árbol lógico por código HW.
Mostrar los elementos que componen el sistema seleccionado.
Mostrar un explorador visual de carpetas.
Mostrar resumen por niveles.
Mostrar contenido directo de la carpeta.
Permitir búsqueda por código, descripción, componente, nombre o ruta.

Dentro de esta pestaña hay dos enfoques:

Árbol lógico
Se construye usando relaciones de código, por ejemplo A01 → A0101 → A010101.
Explorador visual
Recorre la estructura física de carpetas y la presenta con expanders.

La pestaña HW PBS se divide internamente en:

Elemento seleccionado
Búsqueda

Y dentro del elemento seleccionado aparecen subpestañas como:

Árbol lógico
Elementos que lo componen
Explorador visual
Resumen niveles
Contenido directo
modules/HW_LMs.py

Es la pestaña funcional de Listas de Materiales.

Este módulo ya tiene bastante lógica implementada. Su función es buscar, cargar, limpiar, fusionar y mostrar las LMs asociadas al elemento HW seleccionado.

Sus responsabilidades principales son:

Buscar ficheros Excel de LM dentro de las rutas asociadas al elemento seleccionado.
Detectar ficheros con patrón de nombre tipo LMxx_Arevision.
Quedarse con la revisión más reciente de cada LM.
Leer Excel usando engine calamine.
Detectar automáticamente la hoja válida.
Detectar la fila de cabecera.
Normalizar nombres de columnas.
Rellenar columnas faltantes con NOT AVAILABLE.
Eliminar filas vacías o sin datos útiles.
Fusionar todas las LMs cargadas.
Mostrar la tabla de materiales con AgGrid.
Mostrar un log de lectura y fusión.
Exportar a CSV registros con errores en campos prioritarios.

La pestaña LMs responde al elemento seleccionado en el sidebar. Si se selecciona un elemento concreto, busca LMs en sus descendientes. Si se selecciona A00, el código actual trata A00 como suma de los elementos principales existentes del sidebar, evitando procesarlo como una carpeta física normal.

Campos principales que maneja:

CODIGO MATERIAL
CANTIDAD
REF.TOP.
UNIDAD
PROBABILIDAD
DESCRIPCION
P/N
MNF
ELEC/MEC
CHECK BOM
LM_DOC
EDICION
Origen fichero

Además, calcula si hay campos obligatorios incompletos y lo marca en la columna Campos obligatorios incompletos.

modules/HW_BOM.py

Es la pestaña prevista para BOM.

Actualmente está preparada estructuralmente, pero no tiene funcionalidad real implementada. Recibe el DataFrame y el código seleccionado, obtiene el elemento principal seleccionado y muestra un mensaje indicando que el módulo BOM está pendiente de implementación.

Arquitectónicamente ya está conectada al flujo principal, pero funcionalmente es un placeholder.

modules/HW_material_status.py

Es la pestaña prevista para Material Status.

Igual que BOM, está conectada a la app y responde al elemento seleccionado en el sidebar, pero por ahora solo muestra el título del módulo y un mensaje de pendiente de implementación.

modules/HW_assembly_sequence.py

Es la pestaña prevista para Secuencia de Montaje.

También está preparada como módulo independiente. Recibe el DataFrame y el elemento seleccionado, muestra el encabezado de la secuencia de montaje para ese elemento, pero actualmente indica que está pendiente de implementación.

La idea arquitectónica es correcta: cuando se implemente, esta pestaña podrá usar la misma selección global del sidebar que usan HW PBS y LMs.

modules/HW_cross_analysis.py

Es un módulo previsto para análisis cruzado de datos.

Actualmente solo contiene cabecera descriptiva y no tiene funcionalidad implementada.

Tiene sentido como futuro módulo para cruzar PBS, LMs, BOM, Material Status, secuencia, pedidos, costes o documentación.

HW_data_utils.py

Es un módulo previsto para utilidades comunes de datos.

Actualmente está prácticamente vacío y solo contiene una descripción.

Podría ser el sitio natural para mover funciones comunes de limpieza, normalización, validaciones, transformaciones de DataFrames o utilidades compartidas entre LMs, BOM y Material Status.

Qué hace funcionalmente la aplicación ahora

Actualmente la app permite:

Cargar un directorio raíz del simulador.
Detectar carpetas con códigos HW.
Reconstruir una estructura lógica PBS basada en códigos.
Mostrar los elementos principales definidos en el JSON.
Marcar como no encontrados los elementos del JSON que no existan físicamente.
Seleccionar un elemento principal desde el sidebar.
Ver métricas del elemento seleccionado.
Ver su árbol lógico por código.
Inspeccionar nodos del árbol.
Ver carpetas y ficheros asociados.
Ver resumen por niveles.
Buscar elementos por código, descripción, componente, nombre o ruta.
Cargar y fusionar Listas de Materiales asociadas al elemento seleccionado.
Validar campos clave de las LMs.
Exportar errores de LMs a CSV.
Resumen de arquitectura

La separación actual queda así:

Fichero / módulo	Responsabilidad
HW_app.py	Entrada mínima de la aplicación
HW_app_core.py	Orquestación Streamlit, carga de directorio, sidebar global y pestañas
HW_scanner.py	Escaneo físico de carpetas, normalización de códigos y construcción del DataFrame HW
HW_ui_common.py	Tema visual, CSS común y tablas reutilizables
main_hw_elements.json	Catálogo de elementos principales del simulador
modules/HW_PBS.py	Visualización funcional de estructura HW/PBS
modules/HW_LMs.py	Carga, limpieza, fusión y visualización de Listas de Materiales
modules/HW_BOM.py	Placeholder de BOM
modules/HW_material_status.py	Placeholder de estado de material
modules/HW_assembly_sequence.py	Placeholder de secuencia de montaje
modules/HW_cross_analysis.py	Placeholder de análisis cruzado
HW_data_utils.py	Placeholder de utilidades de datos

En conjunto, la app está organizada para que la selección global del sidebar gobierne todas las pestañas, y cada pestaña principal tenga su propio módulo independiente. La parte más madura ahora mismo es HW PBS; la segunda parte funcional ya avanzada es LMs; y el resto de pestañas están preparadas para crecer sin romper la arquitectura actual.