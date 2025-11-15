from dataclasses import dataclass


@dataclass
class Character:
    """Identifies a character with metadata for display."""
    slug: str
    name: str
    description: str
    portrait_path: str  # Relative path from graphics/characters/
