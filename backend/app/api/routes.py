from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.updates import TimeWindow, UpdateListResponse, UpdateSourceItem
from app.services.answer import AnswerService
from app.services.health import DatabaseReadinessChecker, ReadinessCheckError
from app.services.retriever import RetrieverService
from app.services.updates import UpdateService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live", response_model=LivenessResponse)
def health_live() -> LivenessResponse:
    return LivenessResponse()


def get_readiness_checker(db: Session = Depends(get_db)) -> DatabaseReadinessChecker:
    return DatabaseReadinessChecker(db)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def health_ready(
    checker: DatabaseReadinessChecker = Depends(get_readiness_checker),
) -> ReadinessResponse | JSONResponse:
    try:
        checks = checker.check()
    except ReadinessCheckError as error:
        response = ReadinessResponse(status="not_ready", checks=error.checks)
        return JSONResponse(status_code=503, content=response.model_dump())

    return ReadinessResponse(status="ready", checks=checks)


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
    include_sparse: bool = False,
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
        include_sparse=include_sparse,
        start=start,
        end=end,
    )


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    return RetrieverService(db).search(request)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    return AnswerService(db).answer(request)
