"""Analítica del panel del docente y simulador VARK.

Este paquete existe por la migración a React (27-ago-2026). Hasta entonces esta
lógica vivía como funciones privadas dentro de `web/routers/teacher.py`, de modo
que **solo era alcanzable renderizando una plantilla Jinja**: no había forma de
pedir la cobertura curricular o el rendimiento de los quizzes por HTTP. Eso es lo
que hacía cara la migración del panel y lo que `PLAN_DESARROLLO.md` daba por
resuelto al afirmar que "todo pasa por `/api/*`".

Acá está el cálculo, sin HTTP y sin plantillas; `api/routers/analytics.py` lo
expone como JSON y `web/routers/teacher.py` lo sigue usando para renderizar. Es
la misma función en los dos caminos, que es lo único que garantiza que el panel
viejo y el nuevo no se contradigan mientras convivan.
"""
