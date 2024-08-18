from pydantic import Field, BaseModel


class Config(BaseModel):
    url: str
    bots: list[int]
