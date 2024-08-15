from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel, model_validator
# from message import Message



class Sender(BaseModel):
    user_id: int
    nickname: str
    sender_uid: str


