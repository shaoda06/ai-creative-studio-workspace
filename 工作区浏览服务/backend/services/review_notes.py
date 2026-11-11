"""Shared video review fields and atomic project-scoped storage; no adoption semantics."""
from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class DialogueEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    shot: Annotated[str, Field(min_length=1, max_length=128)]
    index: Annotated[int, Field(ge=0)]
    speaker: Annotated[str, Field(max_length=500)]
    original: Annotated[str, Field(max_length=20000)]
    replacement: Annotated[str, Field(max_length=20000)]


class NoteInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    segment: Annotated[str, Field(pattern=r'^P[0-9]{3,}$')]
    stage: Literal['一采', '二采', '后处理', '场次生成']
    run: Annotated[str, Field(pattern=r'^R[0-9]{3,}$')]
    text: Annotated[str, Field(max_length=20000)]
    fileRevision: Annotated[str, Field(min_length=1, max_length=128)]
    roundNumber: Annotated[int, Field(ge=1)] | None = None
    dialogueEdits: list[DialogueEdit] = Field(default_factory=list)

    def key(self) -> str:
        video = f'{self.segment}/{self.stage}/{self.run}'
        return f'round/{self.roundNumber}/{video}' if self.roundNumber is not None else video


class RevisionNote(NoteInput):
    updatedAt: str


class OverallNote(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    number: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(max_length=20000)]
    updatedAt: str


class NoteChange(NoteInput):
    expectedText: Annotated[str, Field(max_length=20000)]
    expectedDialogueEdits: list[DialogueEdit] = Field(default_factory=list)

    def matches(self, existing: RevisionNote | None) -> bool:
        return (existing.text if existing else '') == self.expectedText and (
            'dialogueEdits' not in self.model_fields_set
            or (existing.dialogueEdits if existing else []) == self.expectedDialogueEdits)

    def saved_fields(self, existing: RevisionNote | None) -> dict:
        fields = self.model_dump(exclude={'expectedText', 'expectedDialogueEdits', 'scene'})
        if existing and 'dialogueEdits' not in self.model_fields_set:
            fields['dialogueEdits'] = [item.model_dump() for item in existing.dialogueEdits]
        return fields


class OverallChange(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    number: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(max_length=20000)]
    expectedText: Annotated[str, Field(max_length=20000)]


class ExportChanges(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    notes: list[NoteChange]
    rounds: list[OverallChange]


class NotesChangedError(ValueError):
    pass


class ReviewNotes(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    notes: dict[str, RevisionNote] = Field(default_factory=dict)
    rounds: dict[str, OverallNote] = Field(default_factory=dict)


class ProjectReviewNotes:
    def __init__(self):
        self.lock = RLock()

    def read(self, path: Path):
        with self.lock:
            data = ReviewNotes.model_validate_json(path.read_text('utf-8')) if path.exists() else ReviewNotes()
            if any(key != note.key() for key, note in data.notes.items()) or any(key != str(note.number) for key, note in data.rounds.items()):
                raise ValueError('修改意见的版本标识与条目不一致')
            return data

    def save(self, path: Path, changes: ExportChanges):
        with self.lock:
            data = self.read(path)
            for value, existing in [(note, data.notes.get(note.key())) for note in changes.notes] + [(note, data.rounds.get(str(note.number))) for note in changes.rounds]:
                matches = value.matches(existing) if isinstance(value, NoteChange) else (existing.text if existing else '') == value.expectedText
                if not matches:
                    raise NotesChangedError('意见已在其他页面更新，请保留本页文字，核对最新意见后再保存。')
            updated = datetime.now().astimezone().isoformat(timespec='seconds')
            for value in changes.notes:
                data.notes[value.key()] = RevisionNote(**value.saved_fields(data.notes.get(value.key())), updatedAt=updated)
            for value in changes.rounds:
                data.rounds[str(value.number)] = OverallNote(**value.model_dump(exclude={'expectedText'}), updatedAt=updated)
            if changes.notes or changes.rounds:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.review-', suffix='.tmp', delete=False) as handle:
                        temporary = Path(handle.name)
                        handle.write(json.dumps(data.model_dump(), ensure_ascii=False, indent=2) + '\n')
                    os.replace(temporary, path)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            return data
