# ============================================================
# FORMA-IA — CHARGEMENT DES PROMPTS YAML
# ============================================================

import os
import yaml
from typing import Dict, Any

def load_prompt(file_path: str) -> Dict[str, Any]:
    """
    Charge un prompt depuis un fichier YAML

    Args:
        file_path (str): Chemin vers le fichier YAML

    Returns:
        Dict: Contenu du prompt
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Prompt non trouvé: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_system_prompt(prompt_data: Dict[str, Any]) -> str:
    """
    Construit le prompt système complet à partir des données YAML

    Args:
        prompt_data (Dict): Données du prompt

    Returns:
        str: Prompt système complet
    """
    sections = []
    for key in ["role", "task", "format", "context", "examples", "security"]:
        if key in prompt_data and prompt_data[key]:
            sections.append(prompt_data[key])

    return "\n\n".join(sections)

def load_prompt_from_module(module: str, prompt_name: str) -> Dict[str, Any]:
    """
    Charge un prompt spécifique d'un module

    Args:
        module (str): Nom du module (m1, m2, m5, m6)
        prompt_name (str): Nom du prompt (veille, tdr, formation, etc.)

    Returns:
        Dict: Contenu du prompt
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, "app", "prompts", module, f"{prompt_name}.yaml")
    return load_prompt(file_path)