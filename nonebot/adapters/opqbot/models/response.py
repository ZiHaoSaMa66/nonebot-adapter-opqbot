from datetime import datetime
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


class GroupData(BaseModel):
    CreateTime: datetime
    GroupCnt: int
    GroupCode: int
    GroupName: str
    MemberCnt: int


class GetGroupListResponse(BaseModel):
    GroupLists: List[GroupData]


class MemberLists(BaseModel):
    CreditLevel: int
    GroupCard: Optional[str]
    JoinTime: datetime
    LastSpeakTime: datetime
    Level: int
    MemberFlag: int
    Nick: str
    Uid: str
    Uin: int


class GetGroupMemberListResponse(BaseModel):
    LastBuffer: str
    MemberLists: List[MemberLists]
