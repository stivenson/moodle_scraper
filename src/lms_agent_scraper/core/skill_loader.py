"""Skill loader para cargar y parsear archivos SKILL.md (prompts en tiempo de ejecución)."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Cargador de skills desde archivos SKILL.md.

    Permite cargar prompts desde archivos SKILL.md con frontmatter YAML,
    siguiendo el estándar de agent-skills (System Message + Human Message Template).
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Inicializa el skill loader.

        Args:
            skills_dir: Directorio donde se encuentran los skills.
                        Si None, usa lms_agent_scraper/skills/
        """
        if skills_dir is None:
            current_file = Path(__file__).resolve()
            # core/skill_loader.py -> parent.parent = package root (lms_agent_scraper)
            package_root = current_file.parent.parent
            skills_dir = package_root / "skills"

        self.skills_dir = Path(skills_dir)
        self._cache: Dict[str, Dict] = {}
        self._resource_cache: Dict[Tuple[str, str], str] = {}

        if not self.skills_dir.exists():
            logger.warning("Directorio de skills no encontrado: %s", self.skills_dir)

    def _parse_skill_file(self, skill_path: Path) -> Dict:
        """Parsea un archivo SKILL.md (frontmatter YAML + secciones markdown)."""
        if not skill_path.exists():
            raise FileNotFoundError(f"Archivo skill no encontrado: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")

        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            raise ValueError(
                f"Formato inválido en {skill_path}: no se encontró frontmatter YAML"
            )

        yaml_content = match.group(1)
        markdown_content = match.group(2)

        try:
            metadata = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parseando YAML en {skill_path}: {e}") from e

        if "name" not in metadata:
            raise ValueError(f"Campo 'name' requerido en {skill_path}")
        if "description" not in metadata:
            raise ValueError(f"Campo 'description' requerido en {skill_path}")

        sections = self._parse_markdown_sections(markdown_content)

        return {
            "metadata": metadata,
            "content": markdown_content,
            "sections": sections,
            "path": skill_path,
        }

    def _parse_markdown_sections(self, markdown: str) -> Dict[str, str]:
        """Parsea secciones ## System Message, ## Human Message Template, etc."""
        sections = {}
        section_pattern = r"##\s+([^\n]+)\n(.*?)(?=\n##\s+|\Z)"
        for match in re.finditer(section_pattern, markdown, re.DOTALL):
            section_name = match.group(1).strip().lower().replace(" ", "_")
            section_content = match.group(2).strip()
            sections[section_name] = section_content
        return sections

    def load_skill(self, skill_name: str, use_cache: bool = True) -> ChatPromptTemplate:
        """
        Carga un skill y retorna un ChatPromptTemplate.

        Args:
            skill_name: Nombre del skill (ej: "date-interpreter").
            use_cache: Si usar caché de skills cargados.

        Returns:
            ChatPromptTemplate listo para usar con LangChain.
        """
        if use_cache and skill_name in self._cache:
            skill_data = self._cache[skill_name]
        else:
            skill_path = self.skills_dir / skill_name / "SKILL.md"
            if not skill_path.exists():
                raise FileNotFoundError(
                    f"Skill '{skill_name}' no encontrado en {skill_path}. "
                    "Asegúrate de que el archivo SKILL.md existe."
                )
            skill_data = self._parse_skill_file(skill_path)
            if use_cache:
                self._cache[skill_name] = skill_data

        return self._build_prompt_template(skill_data)

    def _build_prompt_template(self, skill_data: Dict) -> ChatPromptTemplate:
        """Construye ChatPromptTemplate desde los datos del skill."""
        sections = skill_data["sections"]
        messages = []

        if "system_message" in sections:
            messages.append(("system", sections["system_message"]))

        if "human_message_template" in sections:
            messages.append(("human", sections["human_message_template"]))
        elif "human_message" in sections:
            messages.append(("human", sections["human_message"]))

        if not messages:
            raise ValueError(
                f"Skill '{skill_data['metadata']['name']}' no tiene mensajes válidos. "
                "Debe contener al menos '## System Message' y '## Human Message Template'"
            )

        return ChatPromptTemplate.from_messages(messages)

    def get_skill_metadata(self, skill_name: str) -> Dict:
        """Obtiene solo los metadatos de un skill sin cargarlo completamente."""
        if skill_name in self._cache:
            return self._cache[skill_name]["metadata"]
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        skill_data = self._parse_skill_file(skill_path)
        return skill_data["metadata"]

    def load_skill_resource(
        self, skill_name: str, resource_name: str, use_cache: bool = True
    ) -> Optional[str]:
        """
        Carga un recurso (archivo) desde la carpeta de un skill.

        Args:
            skill_name: Nombre del skill (ej: "report-generator").
            resource_name: Nombre del archivo recurso (ej: "report_template.md").
            use_cache: Si usar caché de recursos cargados.

        Returns:
            Contenido del archivo en UTF-8, o None si no existe.
        """
        cache_key = (skill_name, resource_name)
        if use_cache and cache_key in self._resource_cache:
            return self._resource_cache[cache_key]
        resource_path = self.skills_dir / skill_name / resource_name
        if not resource_path.exists() or not resource_path.is_file():
            return None
        content = resource_path.read_text(encoding="utf-8")
        if use_cache:
            self._resource_cache[cache_key] = content
        return content

    def list_available_skills(self) -> List[Dict]:
        """Lista todos los skills disponibles en el directorio."""
        skills = []
        if not self.skills_dir.exists():
            return skills
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    metadata = self.get_skill_metadata(skill_dir.name)
                    skills.append({
                        "name": skill_dir.name,
                        "description": metadata.get("description", ""),
                        "version": metadata.get("version", "1.0.0"),
                        "path": skill_file,
                    })
                except Exception as e:
                    logger.warning("Error cargando skill %s: %s", skill_dir.name, e)
        return skills

    def validate_skill(self, skill_name: str) -> Tuple[bool, Optional[str]]:
        """
        Valida que un skill esté correctamente formateado.

        Para el skill report-generator (solo recurso) comprueba que exista
        report_template.md y placeholders mínimos; no exige System/Human Message.

        Returns:
            Tupla (es_válido, mensaje_error).
        """
        try:
            if skill_name == "report-generator":
                return self._validate_report_generator_skill()

            skill_path = self.skills_dir / skill_name / "SKILL.md"
            if not skill_path.exists():
                return False, f"Archivo no encontrado: {skill_path}"
            skill_data = self._parse_skill_file(skill_path)
            sections = skill_data["sections"]
            if "system_message" not in sections:
                return False, "Falta sección '## System Message'"
            if "human_message_template" not in sections and "human_message" not in sections:
                return False, "Falta sección '## Human Message Template' o '## Human Message'"
            self._build_prompt_template(skill_data)
            return True, None
        except Exception as e:
            return False, str(e)

    def _validate_report_generator_skill(self) -> Tuple[bool, Optional[str]]:
        """Valida el skill report-generator (recurso report_template.md)."""
        skill_dir = self.skills_dir / "report-generator"
        skill_path = skill_dir / "SKILL.md"
        template_path = skill_dir / "report_template.md"
        if not skill_path.exists():
            return False, f"Archivo no encontrado: {skill_path}"
        if not template_path.exists() or not template_path.is_file():
            return False, f"Recurso no encontrado: {template_path}"
        try:
            self._parse_skill_file(skill_path)  # metadata name/description
        except Exception as e:
            return False, str(e)
        template_content = template_path.read_text(encoding="utf-8")
        required_placeholders = ["{title}", "{generation_date}", "{total_tasks}"]
        for placeholder in required_placeholders:
            if placeholder not in template_content:
                return False, f"Falta placeholder {placeholder} en report_template.md"
        return True, None

    def clear_cache(self) -> None:
        """Limpia el caché de skills y de recursos."""
        self._cache.clear()
        self._resource_cache.clear()
        logger.debug("Caché de skills limpiado")
