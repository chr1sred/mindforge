"""Paletas do usuário ("A Minha Cor") e o tema padrão para novos mapas.

Ficam num JSON na pasta de dados do app (sobrevive a atualizações), gravado de forma
atômica. Um arquivo corrompido nunca impede o app de abrir: as paletas são ignoradas.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from mindforge.colorthemes import MAX_CUSTOM, Palette, sanitize_colors, sanitize_setting
from mindforge.i18n import tr
from mindforge.storage.fileio import atomic_write_text

FILE_VERSION = 1


class PaletteStore:
    def __init__(self, path: str):
        self.path = path
        self.palettes: list[Palette] = []
        self.default: Optional[dict] = None       # {"color_theme": {...}, "color_variant": n}
        self.load()

    # ------------------------------------------------------------ arquivo
    def load(self) -> None:
        self.palettes, self.default = [], None
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for item in data.get("palettes") or []:
            if not isinstance(item, dict):
                continue
            colors = sanitize_colors(item.get("colors"))
            name = item.get("name")
            pid = item.get("id")
            if colors and isinstance(name, str) and name.strip() and isinstance(pid, str):
                self.palettes.append(Palette(pid, name.strip()[:60], colors, "custom"))
        d = data.get("default")
        if isinstance(d, dict) and sanitize_setting(d.get("color_theme")):
            v = d.get("color_variant", 0)
            self.default = {"color_theme": sanitize_setting(d["color_theme"]),
                            "color_variant": v if isinstance(v, int) and 0 <= v <= 5 else 0}

    def save(self) -> None:
        data = {"version": FILE_VERSION,
                "palettes": [{"id": p.id, "name": p.name, "colors": list(p.colors)} for p in self.palettes],
                "default": self.default}
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------ paletas
    def find(self, pid: str) -> Optional[Palette]:
        return next((p for p in self.palettes if p.id == pid), None)

    def unique_name(self, name: str, ignore: Optional[str] = None) -> str:
        name = (name or "").strip()[:60] or tr("Personalizado")
        taken = {p.name.casefold() for p in self.palettes if p.id != ignore}
        if name.casefold() not in taken:
            return name
        i = 2
        while f"{name} ({i})".casefold() in taken:
            i += 1
        return f"{name} ({i})"

    def suggested_name(self) -> str:
        i = 1
        taken = {p.name.casefold() for p in self.palettes}
        while tr("Personalizado {n}", n=i).casefold() in taken:
            i += 1
        return tr("Personalizado {n}", n=i)

    def can_add(self) -> bool:
        return len(self.palettes) < MAX_CUSTOM

    def add(self, name: str, colors) -> Palette:
        if not self.can_add():
            raise ValueError(tr("Limite de {n} paletas atingido. Exclua alguma para criar outra.", n=MAX_CUSTOM))
        cols = sanitize_colors(colors)
        if cols is None:
            raise ValueError(tr("A paleta precisa de 6 cores."))
        p = Palette("custom/" + uuid.uuid4().hex[:10], self.unique_name(name), cols, "custom")
        self.palettes.append(p)
        self.save()
        return p

    def update(self, pid: str, name: str, colors) -> Palette:
        cols = sanitize_colors(colors)
        if cols is None:
            raise ValueError(tr("A paleta precisa de 6 cores."))
        for i, p in enumerate(self.palettes):
            if p.id == pid:
                self.palettes[i] = Palette(pid, self.unique_name(name, ignore=pid), cols, "custom")
                self.save()
                return self.palettes[i]
        raise KeyError(pid)

    def duplicate(self, pid: str) -> Palette:
        p = self.find(pid)
        if p is None:
            raise KeyError(pid)
        return self.add(p.name, p.colors)

    def delete(self, pid: str) -> None:
        self.palettes = [p for p in self.palettes if p.id != pid]
        self.save()

    # ------------------------------------------------------- padrão novos mapas
    def set_default(self, color_theme: Optional[dict], variant: int = 0) -> None:
        v = sanitize_setting(color_theme) if color_theme else None
        self.default = {"color_theme": v, "color_variant": int(variant)} if v else None
        self.save()
