# 🐍 Entorno Virtual - Unisimon Scraper

## 📁 Estructura del Proyecto

```
unisimon_scraper/
├── venv/                          # Entorno virtual de Python
├── activate_env.bat               # Script de activación (Windows)
├── .env.example                   # Plantilla de variables (v2)
├── scraper.py                     # Scraper básico (legacy)
├── scraper_hybrid.py              # Scraper híbrido (legacy)
├── scraper_selenium.py            # Scraper con Selenium (legacy)
├── config.py                      # Configuración legacy
├── utils.py                       # Utilidades legacy
├── requirements.txt
├── pyproject.toml                 # Paquete v2 (pip install -e .)
├── profiles/                      # Perfiles YAML por portal (v2)
├── src/lms_agent_scraper/        # LMS Agent Scraper v2 (CLI, MCP, workflow)
├── docs/
├── tests/
├── reports/                       # Reportes generados
└── debug_html/                    # HTML de debug
```

## 🚀 Cómo usar el entorno virtual

### Opción 1: Usar el script de activación (Recomendado)
```bash
# Doble clic en el archivo o ejecutar desde terminal:
activate_env.bat
```

### Opción 2: Activación manual
```bash
# Activar el entorno virtual
venv\Scripts\activate

# Ejecutar el scraper
python scraper_hybrid.py

# Desactivar el entorno
deactivate
```

## 📦 Dependencias Instaladas

El entorno virtual incluye todas las dependencias necesarias:

- **requests>=2.31.0** - Para peticiones HTTP
- **beautifulsoup4>=4.12.0** - Para parsing HTML
- **lxml>=4.9.0** - Parser XML/HTML rápido
- **selenium>=4.15.0** - Para automatización web
- **webdriver-manager>=4.0.0** - Gestión automática de drivers
- **spacy>=3.7.0** - Procesamiento de lenguaje natural
- **es_core_news_sm** - Modelo de español para spaCy

## 🔧 Comandos Útiles

```bash
# Verificar que el entorno esté activo
where python

# Ver paquetes instalados
pip list

# Actualizar dependencias
pip install -r requirements.txt --upgrade

# Instalar nueva dependencia
pip install nombre_paquete

# Generar requirements.txt actualizado
pip freeze > requirements.txt
```

## 📊 Ejecutar el Scraper

Una vez activado el entorno virtual:

```bash
# Scraper híbrido (recomendado)
python scraper_hybrid.py

# Scraper básico con BeautifulSoup
python scraper.py

# Scraper con Selenium completo
python scraper_selenium.py
```

## 🐛 Solución de Problemas

### Error: "python no se reconoce como comando"
- Asegúrate de que el entorno virtual esté activado
- Verifica que Python esté instalado en el sistema

### Error: "ModuleNotFoundError"
- Activa el entorno virtual: `venv\Scripts\activate`
- Reinstala las dependencias: `pip install -r requirements.txt`

### Error de login en el scraper
- Verifica las credenciales en `config.py`
- Asegúrate de tener conexión a internet
- El portal puede estar temporalmente fuera de servicio

## 📝 Notas Importantes

- **Siempre activa el entorno virtual** antes de ejecutar el scraper
- Los reportes se guardan en la carpeta `reports/`
- Los archivos de debug se guardan en `debug_html/`
- El entorno virtual está aislado del sistema Python global

---

*Entorno virtual creado para el proyecto Unisimon Portal Scraper*
