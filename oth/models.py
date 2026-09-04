"""Modèles de données typographiques et conteneurs de texte (Zero dépendance GUI)."""

from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, List


class TextAlignment(Enum):
    """Énumération neutre de l'alignement (Supprime la dépendance vers Qt.AlignmentFlag)."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class VAlign(Enum):
    TOP = auto()
    MIDDLE = auto()
    BOTTOM = auto()


class Overflow(Enum):
    CLIP = auto()
    VISIBLE = auto()
    AUTOFIT_SHRINK = auto()
    AUTOFIT_GROW = auto()


class SizingMode(Enum):
    AUTO_FIT_CONTENT = auto()
    FREE_RESIZE = auto()
    LOCKED = auto()


@dataclass
class Position:
    para: int
    char: int

    def __le__(self, other: Position) -> bool:
        return (self.para, self.char) <= (other.para, other.char)

    def __lt__(self, other: Position) -> bool:
        return (self.para, self.char) < (other.para, other.char)


@dataclass(frozen=True)
class CharFormat:
    """Format de caractère immuable."""
    font_family: str = "Arial"
    font_size: float = 18.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    color: str = "#000000"
    baseline_shift: float = 0.0
    tracking: float = 0.0
    small_caps: bool = False

    def merged(self, **overrides) -> CharFormat:
        return replace(self, **overrides)


@dataclass
class ParagraphFormat:
    """Format au niveau du paragraphe."""
    alignment: TextAlignment = TextAlignment.LEFT
    indent_left: float = 0.0
    indent_right: float = 0.0
    indent_first_line: float = 0.0
    line_spacing: float = 1.0
    space_before: float = 0.0
    space_after: float = 0.0
    bullet: Optional[str] = None


@dataclass
class Run:
    """Séquence contiguë de texte partageant exactement le même formatage (Inspiré de python-pptx)."""
    text: str
    format: CharFormat


class Paragraph:
    """Paragraphe composé d'une liste de Runs contigus optimisés en mémoire."""

    def __init__(
        self,
        text: str = "",
        default_format: Optional[CharFormat] = None,
        pformat: Optional[ParagraphFormat] = None
    ):
        fmt = default_format or CharFormat()
        self.pformat: ParagraphFormat = pformat or ParagraphFormat()
        self.runs: List[Run] = [Run(text, fmt)] if text else []

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)

    def __len__(self) -> int:
        return sum(len(r.text) for r in self.runs)

    def consolidate(self) -> None:
        """Fusionne les Runs adjacents qui partagent le même format et élimine les Runs vides."""
        if not self.runs:
            return

        new_runs: List[Run] = []
        for run in self.runs:
            if not run.text:
                continue
            if new_runs and new_runs[-1].format == run.format:
                new_runs[-1] = Run(new_runs[-1].text + run.text, run.format)
            else:
                new_runs.append(run)

        self.runs = new_runs

    def insert(self, index: int, chars: str, fmt: CharFormat) -> None:
        """Insère du texte à l'index donné en fragmentant proprement les Runs."""
        if not chars:
            return

        if not self.runs:
            self.runs = [Run(chars, fmt)]
            return

        new_runs: List[Run] = []
        current_offset = 0
        inserted = False

        for run in self.runs:
            run_len = len(run.text)
            if not inserted and current_offset <= index <= current_offset + run_len:
                local_idx = index - current_offset
                left = run.text[:local_idx]
                right = run.text[local_idx:]

                if left:
                    new_runs.append(Run(left, run.format))
                new_runs.append(Run(chars, fmt))
                if right:
                    new_runs.append(Run(right, run.format))
                inserted = True
            else:
                new_runs.append(run)

            current_offset += run_len

        if not inserted:
            new_runs.append(Run(chars, fmt))

        self.runs = new_runs
        self.consolidate()

    def delete(self, start: int, end: int) -> None:
        """Supprime l'intervalle de caractères [start, end]."""
        if start >= end or not self.runs:
            return

        new_runs: List[Run] = []
        current_offset = 0

        for run in self.runs:
            run_len = len(run.text)
            r_start = current_offset
            r_end = current_offset + run_len
            current_offset += run_len

            if r_end <= start or r_start >= end:
                new_runs.append(run)
            else:
                left_len = max(0, start - r_start)
                right_start = max(0, end - r_start)
                kept = run.text[:left_len] + run.text[right_start:]
                if kept:
                    new_runs.append(Run(kept, run.format))

        self.runs = new_runs
        self.consolidate()

    def set_format(self, start: int, end: int, **attrs) -> None:
        """Applique une modification de format à une plage de texte."""
        if start >= end or not self.runs:
            return

        new_runs: List[Run] = []
        current_offset = 0

        for run in self.runs:
            run_len = len(run.text)
            r_start = current_offset
            r_end = current_offset + run_len
            current_offset += run_len

            if r_end <= start or r_start >= end:
                new_runs.append(run)
            else:
                overlap_start = max(start, r_start) - r_start
                overlap_end = min(end, r_end) - r_start

                if overlap_start > 0:
                    new_runs.append(Run(run.text[:overlap_start], run.format))

                affected_text = run.text[overlap_start:overlap_end]
                new_fmt = run.format.merged(**attrs)
                new_runs.append(Run(affected_text, new_fmt))

                if overlap_end < run_len:
                    new_runs.append(Run(run.text[overlap_end:], run.format))

        self.runs = new_runs
        self.consolidate()

    def format_at(self, index: int) -> CharFormat:
        if not self.runs:
            return CharFormat()
        current = 0
        for run in self.runs:
            if current <= index < current + len(run.text):
                return run.format
            current += len(run.text)
        return self.runs[-1].format

    def split(self, index: int) -> Paragraph:
        """Découpe le paragraphe en deux au niveau de l'index spécifié."""
        right_p = Paragraph(pformat=ParagraphFormat(**self.pformat.__dict__))
        right_p.runs = []

        new_left_runs: List[Run] = []
        current = 0

        for run in self.runs:
            run_len = len(run.text)
            if current + run_len <= index:
                new_left_runs.append(run)
            elif current >= index:
                right_p.runs.append(run)
            else:
                local_idx = index - current
                left_text = run.text[:local_idx]
                right_text = run.text[local_idx:]
                if left_text:
                    new_left_runs.append(Run(left_text, run.format))
                if right_text:
                    right_p.runs.append(Run(right_text, run.format))
            current += run_len

        self.runs = new_left_runs
        self.consolidate()
        right_p.consolidate()
        return right_p