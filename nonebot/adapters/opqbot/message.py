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
        # print(f">>>>>{self.data}")
        return self.data["text"] if self.is_text() else f"[{self.type}: {self.data}]"

    @staticmethod
    def text(text: str) -> "MessageSegment":
        # print(text)
        return MessageSegment(type="text", data={"text": text})

    @override
    def is_text(self) -> bool:
        return self.type == "text"

    @staticmethod
    def image(
            file: Union[str, bytes, BytesIO, Path],
    ) -> "MessageSegment":
        return MessageSegment(type="image", data={
            "file": file
        })

    @staticmethod
    def voice(
            file: Union[str, bytes, BytesIO, Path],
            voice_time: int = 15,
    ) -> "MessageSegment":
        return MessageSegment(type="voice", data={
            "file": file,
            "VoiceTime": voice_time,
        })

    @staticmethod
    def file(
            filename: str,
            file: Union[str, bytes, BytesIO, Path]
    ) -> "MessageSegment":
        return MessageSegment(type="file", data={
            "file": file,
            "filename": filename
        })


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
        msg = [
            MessageSegment(type="text", data={"text": msg_body.Content})
        ] if msg_body.Content != "" else []  # 文字消息应该只会出现一条或者没有
        if images := msg_body.Images:
            for image in images:
                msg.append(MessageSegment(type="image", data=image.model_dump()))
        elif file := msg_body.File:
            msg.append(MessageSegment(type="file", data=file.model_dump()))
        elif voice := msg_body.Voice:
            msg.append(MessageSegment(type="voice", data=voice.model_dump()))
        return Message(msg) if msg != [] else Message("")
