from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import MovieModel, get_db
from database.models import ActorModel, CountryModel, GenreModel, LanguageModel
from schemas.movies import (MovieCreateSchema, MovieDetailSchema,
                            MovieListResponseSchema, MovieListSchema,
                            MovieUpdateSchema)

router = APIRouter()


def make_rel_link(p: int, per_page: int) -> str:
    return f"{'/theater/movies/'}?page={p}&per_page={per_page}"


async def get_or_create_many(db: AsyncSession, model, names: List[str]):
    out = []
    for name in names or []:
        q = await db.execute(select(model).where(model.name == name))
        obj = q.scalars().first()
        if not obj:
            obj = model(name=name)
            db.add(obj)
            await db.flush()
        out.append(obj)
    return out


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    responses={
        404: {
            "description": "No movies found.",
            "content": {"application/json": {"example": {"detail": "No movies found."}}},
        }
    },
)
async def get_movie_list(
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        per_page: int = Query(10, ge=1, le=20, description="Items per page"),
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    total_items = (await db.execute(select(func.count()).select_from(MovieModel))).scalar_one()
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = math.ceil(total_items / per_page)
    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    order_by = getattr(MovieModel, "default_order_by", lambda: None)()
    stmt = select(MovieModel)
    stmt = stmt.order_by(*order_by) if order_by else stmt.order_by(desc(MovieModel.id))

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    movies = (await db.execute(stmt)).scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    movie_list = [MovieListSchema.model_validate(m) for m in movies]

    prev_url = make_rel_link(page - 1, per_page) if page > 1 else None
    next_url = make_rel_link(page + 1, per_page) if page < total_pages else None

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=prev_url,
        next_page=next_url,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new movie",
    responses={
        201: {"description": "Movie created successfully."},
        400: {
            "description": "Invalid input.",
            "content": {"application/json": {"example": {"detail": "Invalid input data."}}},
        },
        409: {
            "description": "Duplicate movie.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A movie with the name '...' and release date '...' already exists."
                    }
                }
            },
        },
    },
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    existing = await db.execute(
        select(MovieModel).where(
            and_(MovieModel.name == movie_data.name, MovieModel.date == movie_data.date)
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    try:
        country = None
        if movie_data.country:
            r = await db.execute(select(CountryModel).where(CountryModel.code == movie_data.country))
            country = r.scalars().first()
            if not country:
                country = CountryModel(code=movie_data.country)
                db.add(country)
                await db.flush()

        genres = await get_or_create_many(db, GenreModel, movie_data.genres)
        actors = await get_or_create_many(db, ActorModel, movie_data.actors)
        languages = await get_or_create_many(db, LanguageModel, movie_data.languages)

        movie = MovieModel(
            name=movie_data.name,
            date=movie_data.date,
            score=movie_data.score,
            overview=movie_data.overview,
            status=movie_data.status,
            budget=movie_data.budget,
            revenue=movie_data.revenue,
            country=country,
            genres=genres,
            actors=actors,
            languages=languages,
        )
        db.add(movie)
        await db.commit()
        _ = movie.country, movie.genres, movie.actors, movie.languages

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {"example": {"detail": "Movie with the given ID was not found."}}
            },
        }
    },
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = (await db.execute(stmt)).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a movie by ID",
    responses={
        204: {"description": "Movie deleted successfully."},
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {"example": {"detail": "Movie with the given ID was not found."}}
            },
        },
    },
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> Response:
    movie = (await db.execute(select(MovieModel).where(MovieModel.id == movie_id))).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    await db.delete(movie)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/movies/{movie_id}/",
    summary="Update a movie by ID",
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {"application/json": {"example": {"detail": "Movie updated successfully."}}},
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {"example": {"detail": "Movie with the given ID was not found."}}
            },
        },
    },
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    movie = (await db.execute(select(MovieModel).where(MovieModel.id == movie_id))).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    payload = {k: v for k, v in movie_data.model_dump(exclude_unset=True).items() if v is not None}
    for field, value in payload.items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
