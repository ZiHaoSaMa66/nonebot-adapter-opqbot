from typing import Type, Union, Mapping, Iterable

from typing_extensions import override
from pathlib import Path
from io import BytesIO

from nonebot.adapters import Message as BaseMessage, MessageSegment as BaseMessageSegment
from .models import MsgBody


class MessageSegment(BaseMessageSegment["Message"]):

    @classmethod
    @override
    def get_message_class(cls) -> Type["Message"]:
        return Message

    @override
    def __str__(self) -> str:
        return self.data["text"] if self.is_text() else f"[{self.type}: {self.data}]"

    @staticmethod
    def text(text: str) -> "MessageSegment":
        return MessageSegment(type="text", data={"text": text})

    @override
    def is_text(self) -> bool:
        return self.type == "text"

    @staticmethod
    def image(file: Union[str, bytes, BytesIO, Path]) -> "MessageSegment":
        return MessageSegment(type="image", data={
            "file": file
        })

    @staticmethod
    def voice(file: Union[str, bytes, BytesIO, Path], voice_time: int = 15) -> "MessageSegment":
        return MessageSegment(type="voice", data={
            "file": file,
            "VoiceTime": voice_time,
        })

    @staticmethod
    def file(filename: str, file: Union[str, bytes, BytesIO, Path]) -> "MessageSegment":
        return MessageSegment(type="file", data={
            "file": file,
            "filename": filename
        })

    @staticmethod
    def at(uin: int) -> "MessageSegment":
        """
        创建一个 @ 用户段
        :param uin: 用户UIN（QQ号）
        """
        return MessageSegment(type="at", data={"uin": uin})

    @staticmethod
    def atall() -> "MessageSegment":
        """
        创建一个 @全体成员 段
        """
        return MessageSegment(type="atall", data={})



class Message(BaseMessage[MessageSegment]):

    @classmethod
    @override
    def get_segment_class(cls) -> Type[MessageSegment]:
        return MessageSegment

    @staticmethod
    @override
    def _construct(msg: str) -> Iterable[MessageSegment]:
        # print(f">>>>>>>>>>>{msg}")
        yield MessageSegment.text(msg)

    @staticmethod
    def build_message(msg_body: MsgBody) -> "Message":
        msg: list[MessageSegment] = []

        text = msg_body.Content or ""
        if ats := msg_body.AtUinLists:
            # 按照 at 列表逐个替换文本中的 @昵称
            for at in ats:
                nick = at.Nick
                uin = at.Uin
                at_text = f"@{nick}"
                if at_text in text:
                    # 拆成前 + at段 + 后
                    before, _, after = text.partition(at_text)
                    if before:
                        msg.append(MessageSegment.text(before))
                    msg.append(MessageSegment(type="at", data={"uin": at}))
                    text = after
            if text:  # 剩余的普通文本
                msg.append(MessageSegment.text(text))
        elif text:
            msg.append(MessageSegment.text(text))

        if images := msg_body.Images:
            for image in images:
                msg.append(MessageSegment(type="image", data=image.model_dump()))
        elif file := msg_body.File:
            msg.append(MessageSegment(type="file", data=file.model_dump()))
        elif voice := msg_body.Voice:
            msg.append(MessageSegment(type="voice", data=voice.model_dump()))

        print("debug get msg list")
        print(msg)
        return Message(msg) if msg else Message("")

