# CLN Unidad 5 — Integración, pruebas y calidad

**Materia:** Componentes de Lógica de Negocio · FIME UANL
**Actividad 5:** Laboratorio guiado · Unidad 5
**Profesor:** Miguel Ángel Gómez Marroquín
**Equipo 12 (PIA: CleanPro):**

| Integrante | Matrícula |
|---|---|
| Roberto Carlos Sánchez Flores | 2151262 |
| Donovan Adrian Serrato Lores | 2154304 |
| Laura Sofía Vargas Ramírez | 2152053 |

El repositorio parte del proyecto base de pedidos de la Unidad 5 y lo cubre con pruebas automatizadas: unitarias (dominio), de integración (SQLAlchemy) y con dobles de prueba (pasarela de pago y notificador). Además adapta tres reglas del BRD de **CleanPro** (empresa del PIA) usando los datos del paquete del PIA.

## Instalación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
```

## Comandos

| Qué | Comando |
|---|---|
| Todas las pruebas | `python -m pytest -v` |
| Solo un archivo | `python -m pytest tests/test_repository.py -v` |
| Estilo (Ruff) | `python -m ruff check src tests` |
| Cobertura + reporte HTML | `python -m pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80` |
| Ver el reporte HTML | abrir `htmlcov/index.html` en el navegador |
| Regenerar las matrices CSV | `python generar_matrices.py` |

## Arquitectura

```
Prueba ──► Application Service ──► Dominio (reglas)
              │ puertos
              ├── Repositorio ──► SQLAlchemy + SQLite en memoria   (pruebas de integración)
              ├── Pasarela de pago ──► Mock                         (sin cobros reales)
              └── Notificador ──► Mock                              (sin mensajes reales)
```

El dominio (`src/domain.py`, `src/cleanpro/dominio.py`) no importa SQLAlchemy ni servicios externos, por eso se prueba sin base de datos. Las pruebas de integración crean su propia base SQLite **en memoria** en cada prueba y la destruyen al terminar: nunca tocan datos de producción.

```
cln-u5-pruebas/
├── src/
│   ├── domain.py          ← pedidos: descuento VIP, deuda, total positivo, no confirmar dos veces (TDD)
│   ├── application.py     ← checkout con pasarela de pago
│   ├── repository.py      ← SQLAlchemy (commit / rollback)
│   ├── security.py        ← política de cancelación
│   └── cleanpro/          ← adaptación al PIA (dominio, cargador, repositorio, servicio)
├── tests/                 ← unitarias, integración, mocks, seguridad, casos del CSV y CleanPro
├── datos/                 ← CSV del laboratorio y datos/cleanpro (paquete del PIA)
├── docs/                  ← matrices de pruebas CSV y evidencias
├── generar_matrices.py    ← ejecuta los casos y escribe resultado esperado vs real
└── .github/workflows/ci.yml
```

## Pipeline (GitHub Actions)

En cada `push` o `pull_request`: instala dependencias → `ruff check` → `pytest` con cobertura mínima de 80 % → `compileall` → publica el reporte HTML de cobertura como artefacto (`cobertura-html`).

## Ajustes del equipo al proyecto base

Ninguno cambia las reglas de negocio originales:

1. **`pyproject.toml` → `pythonpath = ["."]`.** Las pruebas importan `src`; con `pytest` a secas (como en GitHub Actions) aparecía `ModuleNotFoundError: No module named 'src'`.
2. **Ruff con reglas fijas (`E`, `F`, `I`).** Las versiones recientes de Ruff marcaban 7 errores `I001` (imports desordenados) en el código original; se ordenaron con `ruff check --fix`.
3. **`engine.dispose()`** al final de las dos pruebas originales del repositorio, para cerrar la base en memoria.
4. **Regla nueva con TDD:** `Order.confirm()` rechaza un pedido ya confirmado (`OrderAlreadyConfirmed`, subclase de `ValueError`, mensaje `already confirmed`).

## Matrices de pruebas (`docs/`)

| Archivo | Contenido |
|---|---|
| `matriz_pruebas.csv` | CP01–CP15 del paquete: entrada, tipo (6 éxito, 6 error, 3 límite), esperado, real, estado |
| `matriz_autorizacion.csv` | Rol, propietario, estado, antigüedad y resultado de `can_cancel` |
| `matriz_cleanpro.csv` | 18 casos de CleanPro: 3 reglas × (éxito, error, límite) + persistencia + mock |

## Adaptación al PIA: CleanPro

Reglas tomadas del **BRD del equipo** (Unidad 2) y probadas con el paquete de datos del PIA (`datos/cleanpro`: 40 contratantes, 20 servicios, 60 solicitudes):

| Regla | BRD | Casos |
|---|---|---|
| R1. Programar solo si el cliente aceptó la cotización, con cliente activo, al menos un servicio y servicios habilitados | RB-02 + precondiciones del paquete | CLN-CP01 a CP05 |
| R2. Facturar solo un servicio terminado; si el cliente no permite el acceso tras 15 min, cobrar 50 % | RB-07, RB-11 | CLN-CP06 a CP09 |
| R3. Los cargos adicionales deben autorizarse antes de facturar, y solo el coordinador autoriza | RB-12, RB-14, RB-15 | CLN-CP10 a CP13 |
| Persistencia (SQLAlchemy) y aviso al cliente (mock) | US-03, US-08 | CLN-CP14 a CP18 |

**Diferencias con el modelo propuesto del paquete del PIA** (el paquete pide documentarlas y no reemplazar el BRD):

| Paquete del PIA | BRD de CleanPro (lo que se implementó) |
|---|---|
| `autorizado` | Cliente aceptó la cotización (RB-02) |
| `cliente_activo`, detalle no vacío | Se adoptaron como precondiciones; no estaban en el BRD |
| Recurso `habilitado=0` | No está en el BRD; se adoptó como precondición: un servicio deshabilitado del catálogo predefinido (relacionado con SUP-06) no se programa |
| Estado `COMPLETADO` | Servicio terminado (RB-05, RB-07) |
| No existe | Estado `NO_REALIZADO` con cargo del 50 % (RB-11) |
| `beneficio_referencia` (preferente ≥ 1500 y sin promoción) | No existe en el BRD: no se implementó; el BRD solo contempla 10 % por frecuencia recurrente (RB-03) |
