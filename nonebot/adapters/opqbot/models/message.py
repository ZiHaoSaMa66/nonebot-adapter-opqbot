from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel, model_validator

class C2CTempMessageHead(BaseModel):
    C2CType: int
    Sig: str
    GroupUin: int
    GroupCode: int


class GroupInfo(BaseModel):
    GroupCard: str
    GroupCode: int
    GroupInfoSeq: int
    GroupLevel: int
    GroupRank: int
    GroupType: int
    GroupName: str


class MsgHead(BaseModel):
    FromUin: int
    ToUin: int
    FromType: int  # "消息来源类型 3私聊 2群组 1好友")
    SenderUin: int  # "发送者QQ号")
    SenderNick: str
    MsgType: int
    C2cCmd: int  # 0 收到群消息, 1 发出去消息的回应, 17 群消息被撤回, 349 上下线, 20 被拉群， 212 群解散， 8 上线， 11 好友私聊", )
    MsgSeq: int
    MsgTime: int
    MsgRandom: int
    MsgUid: int
    GroupInfo: Optional[GroupInfo]
    C2CTempMessageHead: Optional[C2CTempMessageHead]


class AtUinList(BaseModel):
    Nick: str
    Uin: int


class Image(BaseModel):
    FileId: int
    FileMd5: str
    FileSize: int
    Url: str
    Width: int
    Height: int


class Video(BaseModel):
    FileMd5: str
    FileSize: int
    Url: str


class Voice(BaseModel):
    FileMd5: str
    FileSize: int
    Url: str


class File(BaseModel):
    FileName: str
    FileSize: int
    PathId: str


class MsgBody(BaseModel):
    SubMsgType: int  # description="0为单一或复合类型消息(文字 At 图片 自由组合), 12 Xml消息 19 Video消息 51 JSON卡片消息",

    Content: str = ""
    AtUinLists: Optional[List[AtUinList]]
    Images: Optional[List[Image]]
    Video: Optional[Video]
    Voice: Optional[Voice]
    File: Optional[File]


class EventData(BaseModel):
    MsgHead: MsgHead
    MsgBody: Optional[MsgBody]


class CurrentPacket(BaseModel):
    EventData: EventData
    EventName: str


class BaseResponse(BaseModel):
    Ret: int = 0
    ErrMsg: Any


class Response(BaseModel):
    CgiBaseResponse: BaseResponse
    ResponseData: Any


class UploadImageResponse(BaseModel):
    FileMd5: str
    FileSize: int
    FileId: Optional[int]
    Height: int = None
    Width: int = None


class UploadResponse(BaseModel):
    FileMd5: str
    FileSize: int
    FileId: Optional[int]
    FileToken: Optional[str]


class SendMsgResponse(BaseModel):
    MsgTime: int
    MsgSeq: int


