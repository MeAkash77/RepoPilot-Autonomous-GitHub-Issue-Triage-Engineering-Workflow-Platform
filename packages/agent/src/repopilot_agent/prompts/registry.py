"""Prompt registry: markdown files with YAML frontmatter.

Prompts are code: versioned in git, loaded once, version string logged to
Langfuse with every span so any trace can be tied to the exact prompt.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    body: str

    def render(self, **kwargs: str) -> str:
        return self.body.format(**kwargs)


def load_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    raw = path.read_text()
    if not raw.startswith("---"):
        raise ValueError(f"prompt {name} missing frontmatter")
    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter)
    return Prompt(name=name, version=str(meta["version"]), body=body.strip())
