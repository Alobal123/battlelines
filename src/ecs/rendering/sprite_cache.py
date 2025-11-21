from __future__ import annotations

from pathlib import Path
from typing import Any


class SpriteCache:
    """Manages cached sprites and textures shared across renderers."""

    def __init__(self, texture_dir: Path):
        self._texture_dir = Path(texture_dir)
        self._smoothed_texture_cache: dict[tuple[str, int | None], Any] = {}
        self._tile_sprite_map: dict[int, Any] = {}
        self._tile_sprites: Any | None = None
        self._bank_sprite_map: dict[tuple[int, str], Any] = {}
        self._bank_sprites: Any | None = None
        self._choice_cost_sprite_map: dict[tuple[int, int], Any] = {}
        self._choice_cost_sprites: Any | None = None
        self._ability_cost_sprite_map: dict[tuple[int, int], Any] = {}
        self._ability_cost_sprites: Any | None = None
        self._regiment_sprite_map: dict[int, Any] = {}
        self._regiment_sprites: Any | None = None
        self._portrait_sprite_map: dict[str, Any] = {}
        self._portrait_sprites: Any | None = None

    # ------------------------------------------------------------------
    # Board tile sprites
    # ------------------------------------------------------------------
    def cleanup_tile_sprites(self, active_entities: set[int]) -> None:
        if not self._tile_sprite_map:
            return
        stale = [ent for ent in self._tile_sprite_map.keys() if ent not in active_entities]
        for ent in stale:
            self.remove_tile_sprite(ent)

    def ensure_tile_sprite(self, arcade_module, entity: int, type_name: str):
        if not type_name:
            return None
        tile_list = self._tile_sprites
        if tile_list is None:
            tile_list = arcade_module.SpriteList()
            self._tile_sprites = tile_list
        sprite = self._tile_sprite_map.get(entity)
        current_type = getattr(sprite, "_tile_type_name", None) if sprite is not None else None
        if sprite is not None and current_type != type_name:
            self.remove_tile_sprite(entity)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            sprite._tile_type_name = type_name  # type: ignore[attr-defined]
            self._tile_sprite_map[entity] = sprite
            tile_list.append(sprite)
        return sprite

    def remove_tile_sprite(self, entity: int) -> None:
        sprite = self._tile_sprite_map.pop(entity, None)
        if sprite is not None:
            sprite.remove_from_sprite_lists()

    def draw_tile_sprites(self) -> None:
        if self._tile_sprites is not None:
            self._tile_sprites.draw()

    # ------------------------------------------------------------------
    # Bank sprites (per bank entity + type)
    # ------------------------------------------------------------------
    def ensure_bank_sprite(self, arcade_module, bank_entity: int, type_name: str):
        if not type_name:
            return None
        bank_list = self._bank_sprites
        if bank_list is None:
            bank_list = arcade_module.SpriteList()
            self._bank_sprites = bank_list
        key = (bank_entity, type_name)
        sprite = self._bank_sprite_map.get(key)
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            self._bank_sprite_map[key] = sprite
            bank_list.append(sprite)
        return sprite

    def draw_bank_sprites(self) -> None:
        if self._bank_sprites is not None:
            self._bank_sprites.draw()

    # ------------------------------------------------------------------
    # Ability/choice window cost sprites (per option + slot)
    # ------------------------------------------------------------------
    def ensure_choice_cost_sprite(self, arcade_module, option_entity: int, slot_index: int, type_name: str):
        if not type_name:
            return None
        choice_list = self._choice_cost_sprites
        if choice_list is None:
            choice_list = arcade_module.SpriteList()
            self._choice_cost_sprites = choice_list
        key = (option_entity, slot_index)
        sprite = self._choice_cost_sprite_map.get(key)
        current_type = getattr(sprite, "_choice_cost_type", None) if sprite is not None else None
        if sprite is not None and current_type != type_name:
            try:
                sprite.remove_from_sprite_lists()
            except Exception:
                pass
            self._choice_cost_sprite_map.pop(key, None)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            sprite._choice_cost_type = type_name  # type: ignore[attr-defined]
            self._choice_cost_sprite_map[key] = sprite
            choice_list.append(sprite)
        return sprite

    def draw_choice_cost_sprites(self) -> None:
        if self._choice_cost_sprites is not None:
            self._choice_cost_sprites.draw()

    def cleanup_choice_cost_sprites(self, active_keys: set[tuple[int, int]]) -> None:
        if not self._choice_cost_sprite_map:
            return
        for key, sprite in list(self._choice_cost_sprite_map.items()):
            if key not in active_keys:
                removed = self._choice_cost_sprite_map.pop(key, None)
                if removed is not None:
                    try:
                        removed.remove_from_sprite_lists()
                    except Exception:
                        pass
        if not self._choice_cost_sprite_map and self._choice_cost_sprites is not None:
            if hasattr(self._choice_cost_sprites, "__len__") and len(self._choice_cost_sprites) == 0:
                self._choice_cost_sprites = None

    # ------------------------------------------------------------------
    # Ability panel cost sprites (per ability entity + slot)
    # ------------------------------------------------------------------
    def ensure_ability_cost_sprite(self, arcade_module, ability_entity: int, slot_index: int, type_name: str):
        if not type_name:
            return None
        ability_list = self._ability_cost_sprites
        if ability_list is None:
            ability_list = arcade_module.SpriteList()
            self._ability_cost_sprites = ability_list
        key = (ability_entity, slot_index)
        sprite = self._ability_cost_sprite_map.get(key)
        current_type = getattr(sprite, "_ability_cost_type", None) if sprite is not None else None
        if sprite is not None and current_type != type_name:
            try:
                sprite.remove_from_sprite_lists()
            except Exception:
                pass
            self._ability_cost_sprite_map.pop(key, None)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, type_name)
            if sprite is None:
                return None
            sprite._ability_cost_type = type_name  # type: ignore[attr-defined]
            self._ability_cost_sprite_map[key] = sprite
            ability_list.append(sprite)
        return sprite

    def draw_ability_cost_sprites(self) -> None:
        if self._ability_cost_sprites is not None:
            self._ability_cost_sprites.draw()

    def cleanup_ability_cost_sprites(self, active_keys: set[tuple[int, int]]) -> None:
        if not self._ability_cost_sprite_map:
            return
        for key, sprite in list(self._ability_cost_sprite_map.items()):
            if key not in active_keys:
                removed = self._ability_cost_sprite_map.pop(key, None)
                if removed is not None:
                    try:
                        removed.remove_from_sprite_lists()
                    except Exception:
                        pass
        if not self._ability_cost_sprite_map and self._ability_cost_sprites is not None:
            if hasattr(self._ability_cost_sprites, "__len__") and len(self._ability_cost_sprites) == 0:
                self._ability_cost_sprites = None

    # ------------------------------------------------------------------
    # Regiment sprites (per regiment entity)
    # ------------------------------------------------------------------
    def cleanup_regiment_sprites(self, active_entities: set[int]) -> None:
        if not self._regiment_sprite_map:
            return
        stale = [ent for ent in self._regiment_sprite_map.keys() if ent not in active_entities]
        for ent in stale:
            sprite = self._regiment_sprite_map.pop(ent, None)
            if sprite is not None:
                sprite.remove_from_sprite_lists()

    def ensure_regiment_sprite(self, arcade_module, entity: int, unit_type: str):
        regiment_list = self._regiment_sprites
        if regiment_list is None:
            regiment_list = arcade_module.SpriteList()
            self._regiment_sprites = regiment_list
        sprite = self._regiment_sprite_map.get(entity)
        current_type = getattr(sprite, "_unit_type", None) if sprite is not None else None
        if sprite is not None and current_type != unit_type:
            sprite.remove_from_sprite_lists()
            self._regiment_sprite_map.pop(entity, None)
            sprite = None
        if sprite is None:
            sprite = self._create_tile_sprite(arcade_module, unit_type)
            if sprite is None:
                return None
            sprite._unit_type = unit_type  # type: ignore[attr-defined]
            self._regiment_sprite_map[entity] = sprite
            regiment_list.append(sprite)
        return sprite

    def draw_regiment_sprites(self) -> None:
        if self._regiment_sprites is not None:
            self._regiment_sprites.draw()

    # ------------------------------------------------------------------
    # Portrait sprites (per label)
    # ------------------------------------------------------------------
    def ensure_portrait_sprite(self, arcade_module, key: str, texture_path: Path):
        portrait_list = self._portrait_sprites
        if portrait_list is None:
            portrait_list = arcade_module.SpriteList()
            self._portrait_sprites = portrait_list
        sprite = self._portrait_sprite_map.get(key)
        if sprite is None:
            if not texture_path.exists():
                return None
            try:
                texture = arcade_module.load_texture(str(texture_path))
            except Exception:
                return None
            try:
                sprite = arcade_module.Sprite()
                sprite.texture = texture
            except Exception:
                return None
            self._portrait_sprite_map[key] = sprite
            portrait_list.append(sprite)
        else:
            # If this sprite was previously removed from sprite lists, re-attach it.
            try:
                sprite_lists = getattr(sprite, "sprite_lists", None)
            except Exception:
                sprite_lists = None
            if (
                portrait_list is not None
                and sprite is not None
                and (not sprite_lists or portrait_list not in sprite_lists)
            ):
                portrait_list.append(sprite)
        return sprite

    def draw_portrait_sprites(self) -> None:
        if self._portrait_sprites is not None:
            self._portrait_sprites.draw()

    def cleanup_portrait_sprites(self, active_keys: set[str]) -> None:
        if not self._portrait_sprite_map:
            return
        for key, sprite in list(self._portrait_sprite_map.items()):
            if key not in active_keys and sprite is not None:
                try:
                    sprite.remove_from_sprite_lists()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def update_sprite_visuals(
        self,
        sprite,
        center_x: float,
        center_y: float,
        icon_size: float,
        alpha: int,
        tint_color=None,
    ) -> None:
        sprite.center_x = center_x
        sprite.center_y = center_y
        texture = sprite.texture
        if texture and texture.width and texture.height:
            max_dim = max(texture.width, texture.height)
            if max_dim:
                sprite.scale = icon_size / max_dim
        sprite.alpha = max(0, min(255, int(alpha)))
        if tint_color is not None and hasattr(sprite, "color") and isinstance(tint_color, tuple):
            r, g, b = tint_color[:3]
            sprite.color = (r, g, b)

    def get_tile_texture(self, arcade_module, type_name: str, *, max_dim: int | None = 96):
        if not type_name:
            return None
        preferred_name = type_name
        texture_path = self._texture_dir / f"{preferred_name}.png"
        if not texture_path.exists() and type_name == "chaos":
            preferred_name = "secrets"
            texture_path = self._texture_dir / f"{preferred_name}.png"
        if not texture_path.exists():
            return None
        return self._load_smoothed_texture(arcade_module, texture_path, max_dim=max_dim)

    def _create_tile_sprite(self, arcade_module, type_name: str):
        preferred_name = type_name
        texture_path = self._texture_dir / f"{preferred_name}.png"
        if not texture_path.exists() and type_name == "chaos":
            # Chaos shares the Secrets icon until a bespoke asset is added.
            preferred_name = "secrets"
            texture_path = self._texture_dir / f"{preferred_name}.png"
        if not texture_path.exists():
            return None
        tex = self._load_smoothed_texture(arcade_module, texture_path, max_dim=96)
        if tex is None:
            return None
        try:
            sprite = arcade_module.Sprite()
            sprite.texture = tex
        except Exception:
            return None
        sprite._tile_type_name = type_name  # type: ignore[attr-defined]
        return sprite

    def _load_smoothed_texture(self, arcade_module, path: Path, max_dim: int | None = None):
        from PIL import Image

        key = (str(path), max_dim)
        cached = self._smoothed_texture_cache.get(key)
        if cached is not None:
            return cached
        if not path.exists():
            return None
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None
        if max_dim is not None and max(img.size) > max_dim:
            w, h = img.size
            scale = max_dim / max(w, h)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resampling = getattr(Image, "Resampling", None)
            if resampling and hasattr(resampling, "LANCZOS"):
                img = img.resize((new_w, new_h), resampling.LANCZOS)
            else:
                img = img.resize((new_w, new_h))
        try:
            texture = arcade_module.Texture(name=f"smooth:{path.name}:{max_dim}", image=img)
        except Exception:
            cache_file = path.parent / f"._smooth_cache_{path.stem}_{max_dim or 'orig'}.png"
            try:
                img.save(cache_file)
                texture = arcade_module.load_texture(cache_file)
            except Exception:
                return None
        self._smoothed_texture_cache[key] = texture
        return texture
