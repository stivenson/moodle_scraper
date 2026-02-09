"""
CLI para LMS Agent Scraper.
"""

import logging
import sys
from pathlib import Path

import typer

app = typer.Typer(name="lms-scraper", help="Framework de agentes para scraping de portales LMS")


def _configure_logging():
    """Configura logging para que los pasos del workflow se vean en consola."""
    root = logging.getLogger("lms_agent_scraper")
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout)
        try:
            h.stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
        h.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(h)


@app.command()
def run(
    profile: str = typer.Option(
        None, "--profile", "-p", help="Perfil YAML a usar (default: PORTAL_PROFILE)"
    ),
):
    """Ejecutar scraper con perfil por defecto o especificado."""
    from lms_agent_scraper.config.settings import PortalSettings, ScraperSettings, OutputSettings
    from lms_agent_scraper.graph.workflow import run_workflow

    portal = PortalSettings()
    scraper = ScraperSettings()
    output = OutputSettings()

    profile_name = profile or portal.profile
    base_url = portal.base_url or ""
    username = portal.username or ""
    password = portal.password or ""

    if not base_url or not username:
        typer.echo("Configure PORTAL_BASE_URL, PORTAL_USERNAME y PORTAL_PASSWORD en .env", err=True)
        raise typer.Exit(1)

    _configure_logging()
    typer.echo(f"Perfil: {profile_name} | URL: {base_url}")
    typer.echo("---")
    result = run_workflow(
        profile_name=profile_name,
        base_url=base_url,
        username=username,
        password=password,
        days_ahead=scraper.days_ahead,
        days_behind=scraper.days_behind,
        max_courses=scraper.max_courses,
        output_dir=str(output.dir),
        profiles_dir=_profiles_dir(),
        debug=scraper.debug_mode,
    )
    typer.echo("---")
    if result.get("errors"):
        for e in result["errors"]:
            typer.echo(f"  [error] {e}", err=True)
    from lms_agent_scraper.tools.report_tools import count_tasks_in_period

    tasks_in_period = count_tasks_in_period(
        result.get("assignments", []),
        result.get("days_ahead", 7),
        result.get("days_behind", 7),
    )
    typer.echo(f"Cursos: {len(result.get('courses', []))} | Tareas: {tasks_in_period}")
    if result.get("report_path"):
        typer.echo(f"Reporte guardado: {result['report_path']}")
    if not result.get("authenticated"):
        typer.echo("Login falló. Revise credenciales y perfil.", err=True)
        raise typer.Exit(1)


profiles_app = typer.Typer(help="Gestión de perfiles YAML")


def _profiles_dir() -> Path:
    # Project root: go up from .../src/lms_agent_scraper/cli.py to repo root
    here = Path(__file__).resolve().parent
    root = here.parent.parent  # .../src -> parent is repo root
    if (root / "profiles").exists():
        return root / "profiles"
    return Path("profiles")


@profiles_app.command("list")
def profiles_list():
    """Listar perfiles disponibles."""
    from lms_agent_scraper.core.profile_loader import ProfileLoader

    loader = ProfileLoader(_profiles_dir())
    try:
        names = loader.list_profiles()
        for n in names:
            typer.echo(n)
    except FileNotFoundError:
        typer.echo("No se encontró el directorio profiles/", err=True)
        raise typer.Exit(1)


@profiles_app.command("validate")
def profiles_validate(
    profile_name: str = typer.Argument(..., help="Nombre del perfil a validar"),
):
    """Validar perfil YAML."""
    from lms_agent_scraper.core.profile_loader import ProfileLoader

    loader = ProfileLoader(_profiles_dir())
    try:
        loader.load(profile_name)
        typer.echo(f"Perfil '{profile_name}' válido.")
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


app.add_typer(profiles_app, name="profiles")

mcp_app = typer.Typer(help="Servidor MCP")


@mcp_app.command("serve")
def mcp_serve():
    """Iniciar servidor MCP."""
    typer.echo("Iniciando servidor MCP... (use python -m lms_agent_scraper.mcp.server)")
    raise typer.Exit(0)


app.add_typer(mcp_app, name="mcp")


if __name__ == "__main__":
    app()
