"""
Course endpoints (for debugging/admin).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import CourseSchema, Course
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/courses/{course_id}", response_model=CourseSchema)
async def get_course(course_id: str, db: AsyncSession = Depends(get_db)):
    """Get course by ID."""
    stmt = select(Course).where(Course.course_id == course_id)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return CourseSchema.from_orm(course)


@router.get("/courses/search", response_model=dict)
async def search_courses(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Search courses by keyword (admin/debug only).
    Returns basic keyword search results.
    """
    stmt = select(Course).where(
        Course.title.ilike(f"%{q}%") | Course.description.ilike(f"%{q}%")
    ).limit(limit)
    
    result = await db.execute(stmt)
    courses = result.scalars().all()
    
    return {
        "query": q,
        "count": len(courses),
        "courses": [CourseSchema.from_orm(c) for c in courses]
    }
