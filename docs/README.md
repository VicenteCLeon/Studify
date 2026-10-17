# Documentación

Qué es cada documento de esta carpeta y cuándo leerlo.

## Por dónde empezar

Para retomar el proyecto no hace falta leer todo:

1. El inicio de [`AVANCE.md`](AVANCE.md), hasta el §1 (unas 90 líneas): qué es el proyecto y en
   qué estado está.
2. [`PENDIENTES.md`](PENDIENTES.md): lo que falta, empezando por lo que hay que cerrar antes del
   piloto, y cómo se trabaja.
3. Las secciones de los documentos de abajo que correspondan a lo que se va a tocar.

## Documentos

| Documento | Qué es | Cuándo leerlo | Se actualiza |
|---|---|---|---|
| [`AVANCE.md`](AVANCE.md) | Bitácora: estado actual al inicio y, en el §5, qué se hizo, qué se encontró y cómo se verificó, en orden. El código cita sus secciones por nombre. | Para el estado general, o para la historia y la evidencia de un tema. | Sí: el estado y una sección nueva por cada avance. |
| [`PENDIENTES.md`](PENDIENTES.md) | La única lista de lo abierto: revisión de código, generación VARK, Fase 5, legal, operación, decisiones con la profesora y extensiones. | Antes de elegir qué hacer. | Sí: lo cerrado se borra y pasa a AVANCE. |
| [`CORRECCIONES_INFORME.md`](CORRECCIONES_INFORME.md) | Qué corregir, actualizar o agregar en el informe final respecto del de avance, por capítulo. | Al escribir el informe final. | Sí: se tacha lo aplicado. |
| [`seminario_titulo.md`](seminario_titulo.md) | El informe de avance entregado (abril de 2026): fuente del diseño. | Para entender de dónde sale una regla o una tabla. | No: es el entregado. |
| [`PLAN_DESARROLLO.md`](PLAN_DESARROLLO.md) | El plan de implementación derivado del informe: stack, fases, contrato original de la cápsula y riesgos. | Para saber por qué el sistema es como es. | Solo notas de estado. |
| [`PRUEBAS_VARK.md`](PRUEBAS_VARK.md) | La batería de pruebas de punta a punta por perfil, los hallazgos H1–H13 con su evidencia, las rondas de corrección, los motores de voz y el análisis de licencias. | Antes de tocar el prompt, el validador o el audio. | Cuando se mide algo nuevo. |
| [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) | Tokens, componentes y convenciones de la interfaz, con el checklist de accesibilidad. | Antes de tocar un template o el CSS. | Cuando cambia la UI. |
| [`modulo-visual/analisis-modulo-visual.md`](modulo-visual/analisis-modulo-visual.md) | Propuesta del recurso visual del perfil V (un SVG dibujado a partir de una especificación del LLM), comparativa de modelos, costos y estimación. Incluye la migración a `deepseek-flash` (§10.8). | Antes de implementar el módulo Visual o de cambiar de modelo. | Mientras siga la propuesta. |

## Carpetas

- [`historico/`](historico/): informes y archivos que ya no describen el estado actual, pero se
  conservan como evidencia. Cada uno dice al inicio qué ya no es cierto.
- `images/`: salidas de los experimentos de generación de imágenes. Las citan el informe de
  FLUX.2 de `historico/` y la tabla de material de origen de `PRUEBAS_VARK.md`.
- `modulo-visual/pruebas/`: scripts, especificaciones y resultados con los que se midió el
  módulo Visual. Los `.md` de `resultados/` los generan esos scripts.
