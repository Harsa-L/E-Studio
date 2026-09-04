"""Gestionnaire d'état du curseur de saisie et d'historique d'édition."""

from __future__ import annotations
from copy import deepcopy
from typing import Optional, Tuple, TYPE_CHECKING

from models import Position, CharFormat, ParagraphFormat

if TYPE_CHECKING:
    from items import TextItem


class TextCursor:
    def __init__(self, obj: TextItem):
        self.obj = obj
        self.position = Position(0, 0)
        self.anchor: Optional[Position] = None
        self.pending_format: Optional[CharFormat] = None
        self._undo_stack = []
        self._redo_stack = []

    def _snapshot(self):
        return deepcopy((self.obj.paragraphs, self.position, self.anchor, self.pending_format))

    def _record_edit(self):
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        snapshot = self._undo_stack.pop()
        self.obj.paragraphs, self.position, self.anchor, self.pending_format = deepcopy(snapshot)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        snapshot = self._redo_stack.pop()
        self.obj.paragraphs, self.position, self.anchor, self.pending_format = deepcopy(snapshot)
        return True

    def has_selection(self) -> bool:
        return self.anchor is not None and self.anchor != self.position

    def selection_range(self) -> Tuple[Position, Position]:
        assert self.has_selection()
        if self.anchor is not None:
            return (self.anchor, self.position) if self.anchor < self.position else (self.position, self.anchor)
        return self.position, self.position

    def insert_text(self, chars: str) -> None:
        if not chars:
            return
        self._record_edit()
        if self.has_selection():
            self._delete_selection()

        fmt = self.pending_format or self._inherited_format_at(self.position)
        parts = chars.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        paragraph = self.obj.paragraphs[self.position.para]
        paragraph.insert(self.position.char, parts[0], fmt)
        self.position.char += len(parts[0])

        for part in parts[1:]:
            right = paragraph.split(self.position.char)
            right.pformat = ParagraphFormat(**paragraph.pformat.__dict__)
            self.obj.paragraphs.insert(self.position.para + 1, right)
            self.position = Position(self.position.para + 1, 0)
            paragraph = right
            paragraph.insert(0, part, fmt)
            self.position.char = len(part)

        self.pending_format = None

    def backspace(self) -> None:
        if not self.has_selection() and self.position.char == 0 and self.position.para == 0:
            return
        self._record_edit()
        if self.has_selection():
            self._delete_selection()
            return

        pos = self.position
        if pos.char > 0:
            p = self.obj.paragraphs[pos.para]
            p.delete(pos.char - 1, pos.char)
            self.position.char -= 1
        elif pos.para > 0:
            prev = self.obj.paragraphs[pos.para - 1]
            cur = self.obj.paragraphs.pop(pos.para)
            join_at = len(prev)
            prev.runs.extend(cur.runs)
            prev.consolidate()
            self.position = Position(pos.para - 1, join_at)

    def _delete_selection(self) -> None:
        start, end = self.selection_range()
        if start.para == end.para:
            self.obj.paragraphs[start.para].delete(start.char, end.char)
        else:
            first = self.obj.paragraphs[start.para]
            last = self.obj.paragraphs[end.para]
            first.delete(start.char, len(first))
            last.delete(0, end.char)
            first.runs.extend(last.runs)
            first.consolidate()
            del self.obj.paragraphs[start.para + 1: end.para + 1]

        self.position = start
        self.anchor = None

    def _inherited_format_at(self, pos: Position) -> CharFormat:
        p = self.obj.paragraphs[pos.para]
        if pos.char > 0:
            return p.format_at(pos.char - 1)
        if len(p) > 0:
            return p.format_at(0)
        return CharFormat()