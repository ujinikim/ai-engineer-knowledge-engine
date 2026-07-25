from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.updates import TimeWindow, UpdateListResponse, UpdateSourceItem
from app.services.answer import AnswerService
from app.services.retriever import RetrieverService
from app.services.updates import UpdateService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/update-sources", response_model=list[UpdateSourceItem])
def update_sources(db: Session = Depends(get_db)) -> list[UpdateSourceItem]:
    return UpdateService(db).list_sources()


@router.get("/updates", response_model=UpdateListResponse)
def updates(
    window: TimeWindow = "week",
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source_names: list[str] | None = Query(default=None),
    tools: list[str] | None = Query(default=None),
    categories: list[str] | None = Query(default=None),
    event_types: list[str] | None = Query(default=None),
    source_types: list[str] | None = Query(default=None),
    maturities: list[str] | None = Query(default=None),
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
) -> UpdateListResponse:
    return UpdateService(db).list_updates(
        window=window,
        limit=limit,
        offset=offset,
        source_names=[source.strip().lower() for source in source_names] if source_names else None,
        tools=tools,
        categories=categories,
        event_types=event_types,
        source_types=source_types,
        maturities=maturities,
        start=start,
        end=end,
    )


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    return RetrieverService(db).search(request)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    return AnswerService(db).answer(request)
