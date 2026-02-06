# Principios SOLID y calidad de código

> **Regla activa:** Esta política está definida en las reglas generales de Cursor (`~/.cursor/rules/solid-and-quality.mdc`, `alwaysApply: true`). Esta copia en el repo sirve de referencia para que el equipo y los agentes la tengan en cuenta al escribir o refactorizar código en este proyecto.

Al escribir o refactorizar código, aplica siempre estos principios.

## SOLID

- **S – Single Responsibility**: Cada clase o función debe tener una única razón para cambiar. Si hace más de una cosa, extrae responsabilidades a otros módulos o funciones.
- **O – Open/Closed**: Abierto a extensión, cerrado a modificación. Preferir composición, herencia bien acotada o estrategias inyectables antes de modificar código existente.
- **L – Liskov Substitution**: Los subtipos deben ser sustituibles por sus tipos base sin romper el contrato (precondiciones, postcondiciones, invariantes).
- **I – Interface Segregation**: Interfaces pequeñas y específicas. El cliente no debe depender de métodos que no usa; preferir varios protocolos/abstractas acotados antes que uno "gordo".
- **D – Dependency Inversion**: Depender de abstracciones (interfaces, protocolos, ABC), no de implementaciones concretas. Inyectar dependencias cuando sea posible.

## Otras prácticas

- **DRY**: No repetir lógica; extraer a funciones o módulos reutilizables.
- **Nombres descriptivos**: Variables, funciones y clases con nombres que expliquen su propósito.
- **Funciones acotadas**: Preferir funciones cortas y enfocadas; si una función hace demasiado, dividirla.

## Ejemplo (Python)

```python
# Evitar: una clase que hace scraping + persistencia + reporte
class Scraper:
    def scrape(self): ...
    def save_to_db(self): ...
    def generate_report(self): ...

# Preferir: responsabilidades separadas, dependencias inyectadas
class Scraper:
    def scrape(self) -> list[dict]: ...

class Repository:
    def save(self, data: list[dict]) -> None: ...

def generate_report(data: list[dict], formatter: ReportFormatter) -> str: ...
```
