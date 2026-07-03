"""AI analyses: queue, list, inspect."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.upload import Upload
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisOut
from app.workers.tasks import analyze_task

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    payload: AnalysisCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    upload = await db.get(Upload, payload.upload_id)
    if upload is None or upload.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    if upload.status != "parsed":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Upload is not parsed yet (status: {upload.status})"
        )
    analysis = Analysis(user_id=user.id, upload_id=upload.id, status="queued")
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    analyze_task.delay(str(analysis.id), payload.instructions)
    return AnalysisOut.model_validate(analysis)


@router.get("", response_model=list[AnalysisOut])
async def list_analyses(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AnalysisOut]:
    rows = (
        await db.execute(
            select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc())
        )
    ).scalars()
    return [AnalysisOut.model_validate(a) for a in rows]


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return AnalysisOut.model_validate(analysis)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    await db.delete(analysis)
    await db.commit()
