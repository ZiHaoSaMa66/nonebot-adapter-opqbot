from io import BytesIO
from typing import Union, Any, TYPE_CHECKING, Optional
from typing_extensions import override

from nonebot.adapters import Bot as BaseBot
from nonebot.message import handle_event
from nonebot.drivers import Request
from .event import Event, EventType, GroupMessageEvent, FriendMessageEvent
from .message import Message, MessageSegment
# from .log import log
import json
from pydantic import BaseModel
import base64
# from pydantic import
from pathlib import Path

if TYPE_CHECKING:
    from .adapter import Adapter
from .utils import FileType, _resolve_data_type, get_image_size
from .models import BaseResponse, Response, UploadImageVoiceResponse, SendMsgResponse
from nonebot.utils import logger_wrapper

log = logger_wrapper("OPQBOT")


class Bot(BaseBot):
    """
    OPQ 协议 Bot 适配。
    """

    @override
    # def __init__(self, adapter: Adapter, self_id: str, **kwargs: Any):
    def __init__(self, adapter, self_id: str, **kwargs: Any):
        super().__init__(adapter, self_id)
        self.adapter = adapter
        self.http_url: str = self.adapter.http_url
        # 一些有关 Bot 的信息也可以在此定义和存储

    async def handle_event(self, event: Union[Event, GroupMessageEvent]) -> None:
        """处理收到的事件。"""
        # if isinstance(event, MessageEvent):
        #     event.message.reduce()
        #     await _check_reply(self, event)
        #     _check_at_me(self, event)
        #     _check_nickname(self, event)
        if event.__type__ == EventType.GROUP_NEW_MSG:
            if event.is_at_msg():
                for at_user in event.at_users:
                    for msg in event.message:
                        if msg.type == "text":
                            msg.data["Content"] = msg.data["Content"].replace(
                                f"@{at_user.nickname}", "")  # 移除 "@昵称"
                            log("INFO", f"移除@昵称 [@{at_user.nickname}]")

        await handle_event(self, event)

    async def baseRequest(
            self,
            method: str,
            funcname: str,
            path: str,
            payload: Optional[dict] = None,
            params: Optional[dict] = None,
            timeout: Optional[int] = None,
    ) -> Optional["Response.ResponseData"]:
        params = params or {}
        params["funcname"] = funcname
        params["qq"] = self.self_id

        ret = None
        log("INFO", f"request to OPQ | params:[{params}] payload:[{payload}]")
        try:
            resp = await self.adapter.request(Request(
                method,
                url=self.http_url + path,
                params=params,
                json=payload,
                timeout=timeout,
            ))
            ret = json.loads(resp.content)
            resp_model = Response(**ret)
            if resp_model.CgiBaseResponse.Ret == 0:
                log("SUCCESS", ret)
            else:
                log("ERROR", ret)
            return resp_model.ResponseData
        except Exception as e:
            print(e)
            log("INFO", f"接口返回数据：{ret}")
            return None

    def build_request(self, request, cmd="MessageSvc.PbSendMsg") -> dict:
        return {"CgiCmd": cmd, "CgiRequest": request}

    async def post(
            self,
            payload: dict,
            funcname: str = "MagicCgiCmd",
            params: Optional[dict] = None,
            path: str = "/v1/LuaApiCaller",
            timeout: Optional[int] = None,
    ):
        return await self.baseRequest(
            method="POST",
            funcname=funcname,
            path=path,
            payload=payload,
            params=params,
            timeout=timeout,
        )

    async def get(
            self,
            funcname: str,
            params: Optional[dict] = None,
            path: str = "/v1/LuaApiCaller",
            timeout: Optional[int] = None,
    ):
        return await self.baseRequest(
            "GET", funcname=funcname, path=path, params=params, timeout=timeout
        )

    async def download_to_bytes(self, url) -> bytes:
        req = Request(
            method="GET",
            url=url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"},
            timeout=15
        )
        res = await self.adapter.request(req)
        return res.content

    async def upload_group_file(
            self,
            group_id: int,
            filename: str,
            file: Union[str, Path, BytesIO, bytes],
            notify: bool = True,
    ):
        data_type, data = _resolve_data_type(file)
        req = {
            "CommandId": 71,
            "FileName": filename,
            "Notify": notify,
            "ToUin": group_id
        }
        if data_type == FileType.TYPE_URL:
            req["FileUrl"] = data
        elif data_type == FileType.TYPE_BASE64:
            req["Base64Buf"] = data
        elif data_type == FileType.TYPE_PATH:
            req["FilePath"] = data
        else:
            raise ValueError("无法识别文件类型")
        request = self.build_request(req, cmd="PicUp.DataUp")
        res = await self.post(request, path="/v1/upload", funcname="", timeout=120)
        return res

    async def upload_image_voice(
            self,
            command_id: int,
            file: Union[str, Path, BytesIO, bytes],
    ) -> UploadImageVoiceResponse:
        data_type, data = _resolve_data_type(file)
        req = {"CommandId": command_id}
        if data_type == FileType.TYPE_URL:
            data = await self.download_to_bytes(data)
            req["Base64Buf"] = base64.b64encode(data).decode()
        elif data_type == FileType.TYPE_BASE64:
            req["Base64Buf"] = data
        elif data_type == FileType.TYPE_PATH:
            req["FilePath"] = data
        else:
            raise ValueError("无法识别文件类型")
        request = self.build_request(req, cmd="PicUp.DataUp")
        res = await self.post(request, path="/v1/upload", funcname="", timeout=60)
        uploadresponse = UploadImageVoiceResponse(**res)
        if command_id in [1, 2]:  # 上传图片的时候
            height, width = get_image_size(data)
            uploadresponse.Height, uploadresponse.Width = height, width
        return uploadresponse

    async def send_group_msg(
            self,
            group_id: int,
            message: Union[str, Message, MessageSegment],
    ) -> Optional[SendMsgResponse]:
        data = await self._message_to_protocol_data(EventType.GROUP_NEW_MSG, message)
        payload = {
                      "ToUin": group_id,
                      "ToType": 2,
                  } | data
        request = self.build_request(payload)
        return await self.post(request)

    async def send_private_msg(
            self,
            user_id: int,
            message: Union[str, Message, MessageSegment],
            group_id: Optional[int] = None
    ) -> Optional[SendMsgResponse]:
        data = await self._message_to_protocol_data(EventType.GROUP_NEW_MSG, message)
        payload = {
                      "ToUin": user_id,
                      "ToType": 3 if group_id else 1
                  } | data
        if group_id:
            payload["GroupCode"] = group_id
        request = self.build_request(payload)
        return await self.post(request)

    async def _message_to_protocol_data(
            self,
            event_type: EventType,
            message: Union[str, Message, MessageSegment]
    ) -> dict:
        message = Message(message)
        Content = ""
        images = []
        for segment in message:
            if segment.type == "text":
                Content += segment.data.get("Content", "")
            elif segment.type == "image":
                if all(segment.get(key) for key in ["fileid", "filemd5", "filesize"]):
                    # 直接从OPQ拿到的图片
                    images.append({
                        "FileId": segment.get("fileid", None),
                        "FileMd5": segment.get("filemd5", None),
                        "FileSize": segment.get("filesize", None),
                        "Height": segment.get("height", None),
                        "Width": segment.get("width", None)
                    })
                else:  # 手动发送的图
                    img = await self.upload_image_voice(2 if event_type == EventType.GROUP_NEW_MSG else 1,
                                                        file=segment.data.get("file"))
                    images.append({
                        "FileId": img.FileId,
                        "FileMd5": img.FileMd5,
                        "FileSize": img.FileSize,
                        "Height": img.Height,
                        "Width": img.Width,
                    })
        payload = {
            "Content": Content,
            "Images": images
        }
        return payload

    @override
    async def send(
            self,
            event: Event,
            message: Union[str, Message, MessageSegment],
            **kwargs: Any,
    ):
        if event.__type__ == EventType.GROUP_NEW_MSG:  # 群聊
            return await self.send_group_msg(
                group_id=event.group_id,
                message=message
            )
        elif event.__type__ == EventType.FRIEND_NEW_MSG:  # 好友和私聊
            return await self.send_private_msg(
                user_id=event.user_id,
                group_id=event.group_id,
                message=message
            )
        else:
            raise ValueError(f"Unknown supped event: {event.__type__}")

    async def reply(
            self,
            event: Event,
            message: Union[str, Message, MessageSegment],
    ) -> SendMsgResponse:
        if event.message_type == "private":
            raise ValueError(f"unsupported message_type: private")
        else:
            data = await self._message_to_protocol_data(event.__type__, message)
            payload = {
                          "ToUin": event.group_id if event.message_type == "group" else event.user_id,
                          "ToType": 2 if event.message_type == "group" else 1,
                          "ReplyTo": {
                              "MsgSeq": event.message_seq,
                              "MsgTime": event.time,
                              "MsgUid": event.message_uid
                          },
                      } | data
            request = self.build_request(payload)
            return await self.post(request)

    # @override
    # async def send(
    #         self,
    #         event: Event,
    #         message: Union[str, Message, MessageSegment],
    #         **kwargs,
    # ) -> Any:
    #     self.call_api()
