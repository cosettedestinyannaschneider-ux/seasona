from pydantic import BaseModel


class ProductCandidate(BaseModel):
    spu_id: int
    sku_id: int | None = None
    name: str
    score: float
    source: str


class IngredientSearchResult(BaseModel):
    ingredient: str
    candidates: list[ProductCandidate]
    missing: bool = False

