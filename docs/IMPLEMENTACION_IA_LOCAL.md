# Implementación de IA Local (Fase 6: Síntesis Multimedia)

Este documento detalla la arquitectura, el enfoque de memoria y el paso a paso de la integración de modelos de IA locales para la síntesis de recursos multimedia (Imagen, Audio y Video). Su propósito es llevar un registro vivo (checklist) del progreso de implementación.

## 🏗️ Arquitectura y Enfoque

El sistema opera con una **arquitectura híbrida**:
1. **Orquestador Lógico y Redactor (Nube):** Se utiliza la API de DeepSeek como motor de razonamiento (RAG Estructurado). Evalúa el perfil VARK, recupera los fragmentos curriculares y redacta la microcápsula base en formato JSON.
2. **Síntesis Multimedia (Local en GPU):** Según lo que el perfil VARK demande (ej. un estudiante Kinestésico que requiere video), el sistema local toma el mando para materializar los recursos.

### El Reto de la Memoria (Sequential Offloading)
Modelos como *FLUX.1 [schnell]* o *Stable Video Diffusion* demandan entre 8GB y 16GB de VRAM. Cargar todos los motores en la tarjeta gráfica al mismo tiempo causaría un desbordamiento de memoria (*Out of Memory* - OOM). 

Para evitarlo, se ha implementado un **Context Manager de Aislamiento de VRAM** (`src/studify/media/memory_manager.py`). Este módulo garantiza que el ciclo de vida de un recurso sea estrictamente secuencial:
- **Cargar** modelo en VRAM.
- **Inferir** (generar recurso).
- **Descargar** explícitamente (`del model`).
- **Limpiar** basura de Python (`gc.collect()`).
- **Vaciar caché CUDA** (`torch.cuda.empty_cache()`).
- **Pasar** al siguiente modelo.

---

## 📋 Paso a Paso (Checklist de Implementación)

### 1. Modificación de Arquitectura en Código
- [x] Agregar grupo de dependencias multimedia en `pyproject.toml` (PyTorch, Diffusers, TTS, Accelerate).
- [x] Crear el gestor de memoria estricta (`src/studify/media/memory_manager.py`).
- [x] Crear los adaptadores para cada modelo de IA:
  - [x] `image.py`: Integración de **FLUX.1 [schnell] FP8** con CPU offload activo.
  - [x] `audio.py`: Integración de **XTTS-v2** para clonación/síntesis de voz.
  - [x] `video.py`: Integración de **Stable Video Diffusion (SVD)** para img2vid.
- [x] Crear el orquestador multimedia (`generator.py`) que lee las reglas VARK de la base de datos y decide qué adaptador ejecutar secuencialmente.
- [x] Interceptar el endpoint `POST /api/capsulas` en `capsules.py` para gatillar la generación multimedia **después** de persistir el texto JSON de DeepSeek y **antes** de retornar la respuesta a la interfaz web.

### 2. Preparación del Entorno Local (Máquina del Desarrollador / Producción)
- [ ] Instalar PyTorch forzando la compilación nativa con aceleración CUDA (GPU).
  - *Comando:* `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`
- [ ] Instalar el bloque de dependencias opcionales multimedia del proyecto.
  - *Comando:* `pip install -e ".[media]"`
- [ ] Autenticar la terminal con Hugging Face (`huggingface-cli login`) utilizando un Access Token para permitir la descarga de modelos Open Weights con restricción de licencia.

### 3. Precarga y Descarga de Modelos (Pesos - .safetensors)
- [x] **Opción A (Automática - On Demand):** Ejecutar una solicitud en la aplicación por primera vez; el código utilizará `diffusers` y `TTS` para descargar los pesos a la caché local. *(Audio XTTS-v2 ya comprobado mediante script de testeo manual `test_voz.py`, parche de seguridad PyTorch 2.6+ aplicado al orquestador)*.
- [ ] **Opción B (Manual):** Crear un script de precarga (ej. `scripts/precargar_media.py`) que inicialice los tres pipelines temporalmente solo para forzar la descarga de los pesos sin necesidad de hacer interactuar la interfaz web.

### 4. Pruebas y Monitoreo de Estrés (Hardware)
- [ ] Monitorear el uso de VRAM (con `nvidia-smi` o Administrador de Tareas) durante la generación de una cápsula 100% multimodal (V+A+K).
- [ ] Validar que la VRAM se purga completamente a < 2GB (o nivel base inactivo) entre el salto de generación de Imagen -> Audio -> Video.
- [ ] Implementar un mecanismo de *fallback* visual en la interfaz: Si el motor de video explota por hardware insuficiente, la interfaz web debe capturar la falla limpiamente y renderizar al menos el texto y la imagen. *(Actualmente el endpoint captura la excepción y retorna el texto en JSON de DeepSeek para no romper la experiencia, pero falta validarlo en UI).*

