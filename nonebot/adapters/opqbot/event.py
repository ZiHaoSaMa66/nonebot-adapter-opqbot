from datetime import datetime

from typing_extensions import override
from typing import Optional, List, Union, TypeVar, Type, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator
from enum import Enum
from nonebot.utils import escape_tag

from nonebot.adapters import Event as BaseEvent
from nonebot.compat import model_dump
from .models import MsgBody, CurrentPacket
from .message import Message, MessageSegment


class EventType(str, Enum):
    LOGIN_SUCCESS = "ON_EVENT_LOGIN_SUCCESS"
    NETWORK_CHANGE = "ON_EVENT_NETWORK_CHANGE"
    GROUP_NEW_MSG = "ON_EVENT_GROUP_NEW_MSG"
    GROUP_MSG_REVOKE = "ON_EVENT_GROUP_MSG_REVOKE"
    FRIEND_NEW_MSG = "ON_EVENT_FRIEND_NEW_MSG"
    FRIEND_SYSTEM_MSG_NOTIFY = "ON_EVENT_FRIEND_SYSTEM_MSG_NOTIFY"
    GROUP_JOIN = "ON_EVENT_GROUP_JOIN"
    GROUP_EXIT = "ON_EVENT_GROUP_EXIT"
    GROUP_SYSTEM_MSG_NOTIFY = "ON_EVENT_GROUP_SYSTEM_MSG_NOTIFY"
    GROUP_INVITE = "ON_EVENT_GROUP_INVITE"


class Sender(BaseModel):
    user_id: int
    nickname: str
    user_uid: str


class MessageId(BaseModel):
    seq: int
    time: int
    uid: int


class Event(BaseEvent):
    @override
    def get_type(self) -> str:
        return "event"

    @override
    def get_event_name(self) -> str:
        # 返回事件的名称，用于日志打印
        return "event"

    @override
    def get_event_description(self) -> str:
        return escape_tag(str(model_dump(self)))

    @override
    def get_message(self):
        raise ValueError("Event has no message!")

    @override
    def get_user_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def get_session_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def is_tome(self) -> bool:
        raise ValueError("Event has no context!")


class MessageEvent(Event):
    """Event"""
    __type__: EventType
    CurrentQQ: int  # "Bot QQ号")
    CurrentPacket: CurrentPacket
    time: datetime
    message_type: str
    # sub_type: str
    group_id: Optional[int]
    user_id: int
    group_name: Optional[str]
    message: Message = Message()
    message_id: MessageId
    message_random: int
    raw_message: dict
    sender: Sender

    @override
    def get_event_name(self) -> str:
        return self.__type__.name

    @override
    def get_type(self) -> str:
        return "meta_event"

    @override
    def get_event_description(self) -> str:
        return escape_tag(str(model_dump(self)))

    @override
    def get_message(self) -> Message:
        # 返回事件消息对应的 NoneBot Message 对象
        # print(self.get_content())
        return self.message

    @override
    def get_user_id(self) -> str:
        return str(self.user_id)

    @override
    def get_session_id(self) -> str:
        return f"{self.group_id}_{self.user_id}"

    @override
    def is_tome(self) -> bool:
        return False

    def get_from_uin(self):
        return self.get_msg_head().FromUin

    def get_sender_uin(self):
        return self.get_msg_head().SenderUin

    def get_content(self):
        if self.get_msg_body():
            return self.get_msg_body().Content
        return None

    def get_from_type(self):
        return self.get_msg_head().FromType

    @model_validator(mode='before')
    def transform_data(cls, values: dict):
        # 展平嵌套数据
        def flatten_and_update(target: Dict[str, Any], source: Dict[str, Any], new_key: str, keys: list):
            """将嵌套字典展平并更新到目标字典，使用不同的字段名"""
            nested = source
            for key in keys:
                if nested:
                    nested = nested.get(key, {})
            target[new_key] = nested

        values["raw_message"] = values.copy()
        event_data = values.get('CurrentPacket', {}).get('EventData', {})
        msg_head = event_data.get('MsgHead', {})
        msg_body = event_data.get('MsgBody', {}) or {}  # 防止MsgBody:null
        transform_dict = {
                             "time": ["MsgTime"],
                             "user_id": ["SenderUin"],
                             "group_name": ["GroupInfo", "GroupName"],
                             "message_random": ["MsgRandom"],
                         } | ({"group_id": ["GroupInfo", "GroupCode"]} if msg_head.get("GroupInfo")
                              else {"group_id": ['C2CTempMessageHead', 'GroupCode']})  # 需要提取的字段
        for k, v in transform_dict.items():
            flatten_and_update(values, msg_head, k, v)
            # flatten_and_update(values, event_data, "raw_message", ["MsgBody"])
        values["message_type"] = {1: "friend", 2: "group", 3: "private"}.get(msg_head.get("FromType"), "unknown")
        values["message_id"] = MessageId(
            seq=msg_head.get('MsgSeq'),
            time=msg_head.get('MsgTime'),
            uid=msg_head.get('MsgUid')
        )
        values["sender"] = Sender(
            user_id=msg_head.get('SenderUin'),
            nickname=msg_head.get('SenderNick'),
            user_uid=msg_head.get('SenderUid'),
        )  # 发送消息的人
        if body := msg_body:
            values["message"] = Message.build_message(MsgBody(**body))
        else:
            values["message"] = Message()
        return values

    # @field_validator('time', mode='before')
    # def validate_time(cls, v):
    #     return datetime.fromtimestamp(v)

    # @field_validator('message', mode='after')
    # def validate_message(cls, v, values):
    #     cls.build_message()
    #     return v
    #     # 解析不到消息就塞一条空文本


E = TypeVar("E", bound="Event")

EVENT_CLASSES: Dict[str, Type[Event]] = {}


def register_event_class(event_class: Type[E]) -> Type[E]:
    EVENT_CLASSES[event_class.__type__.value] = event_class
    return event_class


@register_event_class
class GroupMessageEvent(MessageEvent):
    """群消息事件"""
    __type__ = EventType.GROUP_NEW_MSG
    at_users: Optional[List[Sender]]

    @override
    def get_type(self) -> str:
        return "message"

    @override
    def is_tome(self) -> bool:
        for at_user in self.at_users:
            if self.CurrentQQ == at_user.user_id:
                return True
        return False

    def is_at_msg(self) -> bool:
        if self.at_users:
            return True
        return False

    @model_validator(mode='before')
    def transform_group_data(cls, values: dict):
        # 展平嵌套数据
        event_data = values.get('CurrentPacket', {}).get('EventData', {})
        msg_body = event_data.get('MsgBody', {}) or {}  # 防止MsgBody:null
        at_uin_lists = msg_body.get("AtUinLists") or []
        at_users = []
        for at_user in at_uin_lists:
            at_users.append(Sender(
                user_id=at_user.get('Uin'),
                nickname=at_user.get('Nick'),
                user_uid=at_user.get('Uid'),
            ))

        values["at_users"] = at_users
        return values


@register_event_class
class FriendMessageEvent(MessageEvent):
    """好友消息事件"""
    __type__ = EventType.FRIEND_NEW_MSG

    @override
    def get_type(self) -> str:
        return "message"


class NoticeEvent(Event):
    """通知类"""
    __type__ = EventType
    CurrentQQ: int  # "Bot QQ号")

    @override
    def get_type(self) -> str:
        return "notice"

    @override
    def get_event_name(self) -> str:
        return self.__type__.name

    @override
    def get_event_description(self) -> str:
        return escape_tag(str(model_dump(self)))

    @override
    def get_message(self) -> Message:
        raise ValueError("Event has no context!")

    @override
    def get_user_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def get_session_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def is_tome(self) -> bool:
        raise ValueError("Event has no context!")


@register_event_class
class GroupMessageRevokeEvent(NoticeEvent):
    """群撤回事件"""
    __type__ = EventType.GROUP_MSG_REVOKE

    @override
    def get_type(self) -> str:
        return "notice"



@register_event_class
class BotLogin(NoticeEvent):
    """Bot登录事件"""
    __type__ = EventType.LOGIN_SUCCESS
    CurrentQQ: int  # "Bot QQ号")

    @override
    def get_type(self) -> str:
        return "notice"

    @override
    def get_event_name(self) -> str:
        return self.__type__.name

    @override
    def get_event_description(self) -> str:
        return escape_tag(str(model_dump(self)))

    @override
    def get_message(self) -> Message:
        raise ValueError("Event has no context!")

    @override
    def get_user_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def get_session_id(self) -> str:
        raise ValueError("Event has no context!")

    @override
    def is_tome(self) -> bool:
        raise ValueError("Event has no context!")
