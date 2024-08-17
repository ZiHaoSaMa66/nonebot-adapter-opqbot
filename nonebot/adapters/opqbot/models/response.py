from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel, model_validator


class BaseResponse(BaseModel):
    Ret: int = 0
    ErrMsg: Any


class Response(BaseModel):
    CgiBaseResponse: BaseResponse
    ResponseData: Any


class UploadImageVoiceResponse(BaseModel):
    FileMd5: str
    FileSize: int
    FileId: Optional[int]
    FileToken: Optional[str] = None
    Height: int = None
    Width: int = None


# class UploadGroupFileResponse(BaseModel):
#     CgiBaseResponse
# ResponseData


class SendMsgResponse(BaseModel):
    MsgTime: int
    MsgSeq: int


class UploadForwardMsgResponse(BaseModel):
    ResId: str
