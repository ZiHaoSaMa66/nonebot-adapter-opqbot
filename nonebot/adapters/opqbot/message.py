from typing import Type, Union, Mapping, Iterable

from typing_extensions import override
from pathlib import Path
from io import BytesIO

from nonebot.adapters import Message as BaseMessage, MessageSegment as BaseMessageSegment
from models import MsgBody


class MessageSegment(BaseMessageSegment["Message"]):

    @classmethod
    @override
    def get_message_class(cls) -> Type["Message"]:
        return Message

    @override
    def __str__(self) -> str:
        # print(f">>>>>{self.data}")
        return self.data["Content"] if self.is_text() else f"[{self.type}: {self.data}]"

    @staticmethod
    def text(text: str) -> "MessageSegment":
        # print(text)
        return MessageSegment(type="text", data={"Content": text})

    @override
    def is_text(self) -> bool:
        return self.type == "text"

    @staticmethod
    def image(
            file: Union[str, bytes, BytesIO, Path],
            *,
            fileid: int = None,
            filemd5: str = None,
            filesize: int = None,
            width: int = None,
            height: int = None
    ) -> "MessageSegment":
        return MessageSegment(type="image", data={
            "file": file,
            "fileid": fileid,
            "filemd5": filemd5,
            "filesize": filesize,
            "height": height,
            "width": width
        })

    @staticmethod
    def voice(
            file: Union[str, bytes, BytesIO, Path],
            *,
            filemd5: str = None,
            filesize: int = None,
            filetoken: str = None
    ) -> "MessageSegment":
        return MessageSegment(type="voice", data={
            "fileid": "22.jpg",
            "FileSize": "",
            "url": url,
            "filetoken": filetoken
        })


    @staticmethod
    def file(file: Union[str, bytes, BytesIO, Path], ) -> "MessageSegment":
        return MessageSegment(type="file", data={
            "FilePath": "22.jpg",
            "FileUrl": "",
            "Base64Buf": ""
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
        msg = [MessageSegment.text(msg_body.Content)] if msg_body.Content else []  # 文字消息应该只会出现一条或者没有
        if images := msg_body.Images:
            for image in images:
                # msg.append(MessageSegment(type="image", data={"file": image.Url, "filemd5": image.FileMd5,
                #                                               "filesize": image.FileSize, "width": image.Width,
                #                                               "height": image.Height}))
                # msg.append(MessageSegment(type="image", data=image.model_dump()))
                msg.append(MessageSegment.image(file=image.Url, fileid=image.FileId, filemd5=image.FileMd5,
                                                filesize=image.FileSize,
                                                width=image.Width, height=image.Height))
        # if file :=body.File:
        #     msg.append(MessageSegment.file())
        return Message(msg) if msg != [] else Message(MessageSegment.text(""))
