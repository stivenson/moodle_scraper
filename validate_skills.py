"""Valida que los skills (SKILL.md) se carguen correctamente y tengan las variables esperadas."""

import sys
from pathlib import Path

# Permitir importar el paquete cuando se ejecuta desde la raíz del repo
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lms_agent_scraper.core.skill_loader import SkillLoader


EXPECTED_VARIABLES = {
    "date-interpreter": ["date_text", "context"],
    "course-extractor": ["snippet", "base_url"],
    "course-page-classifier": ["snippet", "url"],
    "selector-suggester": ["error_message", "html_snippet"],
    "html-structure-analyzer": ["snippet"],
}


def validate_skill(skill_name: str, expected_vars: list, skill_loader: SkillLoader) -> bool:
    """Valida un skill: formato y variables en Human Message Template."""
    print(f"\n=== Validando skill {skill_name} ===")
    try:
        is_valid, error = skill_loader.validate_skill(skill_name)
        if not is_valid:
            print(f"  Skill inválido: {error}")
            return False
        print("  Skill válido (formato y secciones OK)")

        prompt = skill_loader.load_skill(skill_name)
        messages = prompt.messages
        print(f"  Mensajes: {len(messages)} (system y human)")

        human_msg = ""
        if len(messages) > 1:
            human_msg = str(messages[1].prompt.template)
        for var in expected_vars:
            if "{" + var + "}" in human_msg:
                print(f"  Variable {{{var}}} encontrada")
            else:
                print(f"  Variable {{{var}}} NO encontrada en Human Message Template")
                return False
        print(f"  OK {skill_name}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def list_all_skills(skill_loader: SkillLoader) -> bool:
    """Lista todos los skills disponibles."""
    print("\n=== Skills disponibles ===")
    try:
        skills = skill_loader.list_available_skills()
        if not skills:
            print("  No se encontraron skills")
            return False
        for s in skills:
            print(f"  - {s['name']}: {s['description'][:60]}...")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main() -> int:
    print("=" * 60)
    print("VALIDACIÓN DE SKILLS (runtime prompts)")
    print("=" * 60)

    skill_loader = SkillLoader()
    if not skill_loader.skills_dir.exists():
        print(f"\nDirectorio de skills no encontrado: {skill_loader.skills_dir}")
        print("Ejecuta desde la raíz del repo con el paquete en PYTHONPATH (ej. pip install -e .).")
        return 1

    results = []
    results.append(list_all_skills(skill_loader))

    for skill_name, expected_vars in EXPECTED_VARIABLES.items():
        results.append(validate_skill(skill_name, expected_vars, skill_loader))

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Validaciones exitosas: {passed}/{total}")
    if passed == total:
        print("Todos los skills están correctamente implementados.")
        return 0
    print("Algunas validaciones fallaron.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
