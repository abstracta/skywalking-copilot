import json
import os
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader

assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')
templates_repo = Environment(loader=FileSystemLoader(assets_path))
templates_repo.filters['json'] = json.dumps


def solve_response(name: str, ctx: Dict[str, Any]) -> str:
    return solve_template(f"responses/{name}.md", ctx)


def solve_template(file_name: str, context: Dict[str, Any]) -> str:
    return templates_repo.get_template(file_name).render(**context)
