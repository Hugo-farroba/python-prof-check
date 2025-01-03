from sqlmodel import SQLModel, Field
from typing import Optional

class BlockedUsername(SQLModel, table=True):
    username: str = Field(primary_key=True)