from datetime import date, datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from database.models import MovieStatusEnum


def validate_date(release_date: date) -> date:
    if release_date > (date.today() + timedelta(days=365)):
        raise ValueError("Date must be within 365 days from today")
    return release_date


class LanguageSchema(BaseModel):
    id: int
    name: str
    model_config = {
        "from_attributes": True,
    }


class CountrySchema(BaseModel):
    id: int
    code: str
    name: Optional[str]

    model_config = {
        "from_attributes": True
    }


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class ActorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)

    model_config = {
        "from_attributes": True
    }

    @field_validator("date")
    @classmethod
    def validate_date(cls, value):
        current_year = datetime.now().year
        if value.year > current_year + 1:
            raise ValueError(f"Year can`t be greater than {current_year + 1}")
        return value


class MovieDetailSchema(MovieBaseSchema):
    id: int
    country: CountrySchema
    genres: List[GenreSchema]
    actors: List[ActorSchema]
    languages: List[LanguageSchema]

    model_config = {
        "from_attributes": True
    }


class MovieListSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str

    model_config = {
        "from_attributes": True
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)


class MovieCreateSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str
    genres: List[str] = []
    actors: List[str] = []
    languages: List[str] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        if value is None:
            return value
        value = value.upper()
        if len(value) > 3:
            raise ValueError("country must be up to 3-letter ISO alpha-3 code")
        return value

    @field_validator("genres", "actors", "languages", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.title() for item in value]

    @field_validator("date")
    @classmethod
    def date_limit(cls, value: date) -> date:
        return validate_date(value)


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)

    model_config = {
        "from_attributes": True
    }

    @field_validator("date")
    @classmethod
    def date_limit(cls, value: Optional[date]) -> Optional[date]:
        return value if not value else validate_date(value)
