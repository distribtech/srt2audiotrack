from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, HTTPException
from filelock import FileLock
from pydantic import BaseModel, Field

app = FastAPI(title="Subtitle Vocabulary Service", version="1.0.0")

DATA_DIR = Path("/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "vocabulary.db"
LOCK_PATH = Path("/tmp/subtitles_service.lock")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vocabulary (
    token TEXT PRIMARY KEY,
    occurrences INTEGER NOT NULL
)
"""

TOKEN_REGEX = re.compile(r"[\w']+")


class SubtitleRequest(BaseModel):
    subtitle_text: str = Field(..., description="Raw subtitle text, e.g. from an SRT file")


class SubtitleResponse(BaseModel):
    unique_tokens: int
    total_tokens: int


class VocabularyResponse(BaseModel):
    tokens: list[tuple[str, int]]


def _initialise_database() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


_initialise_database()


def _upsert_tokens(conn: sqlite3.Connection, tokens: Iterable[str]) -> None:
    for token in tokens:
        conn.execute(
            """
            INSERT INTO vocabulary(token, occurrences) VALUES (?, 1)
            ON CONFLICT(token) DO UPDATE SET occurrences = occurrences + 1
            """,
            (token,),
        )


@app.post("/subtitles", response_model=SubtitleResponse)
def add_subtitles(payload: SubtitleRequest) -> SubtitleResponse:
    text = payload.subtitle_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="subtitle_text must not be empty")

    tokens = [token.lower() for token in TOKEN_REGEX.findall(text)]
    total_tokens = len(tokens)

    lock = FileLock(str(LOCK_PATH))
    with lock:
        with sqlite3.connect(DB_PATH) as conn:
            _upsert_tokens(conn, tokens)
            conn.commit()
            with closing(conn.cursor()) as cursor:
                cursor.execute("SELECT COUNT(*) FROM vocabulary")
                unique_tokens = cursor.fetchone()[0]

    return SubtitleResponse(unique_tokens=unique_tokens, total_tokens=total_tokens)


@app.get("/vocabulary", response_model=VocabularyResponse)
def get_vocabulary() -> VocabularyResponse:
    lock = FileLock(str(LOCK_PATH))
    with lock:
        with sqlite3.connect(DB_PATH) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute("SELECT token, occurrences FROM vocabulary ORDER BY occurrences DESC")
                tokens = cursor.fetchall()

    return VocabularyResponse(tokens=[(row[0], row[1]) for row in tokens])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
