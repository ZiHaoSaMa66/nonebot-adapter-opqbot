from io import BytesIO
from typing import Union, Any, TYPE_CHECKING, Optional, List, Annotated

# import bot
from typing_extensions import override

from nonebot.adapters import Bot as BaseBot
from nonebot.message import handle_event
from nonebot.drivers import Request
from .event import Event, EventType, GroupMessageEvent, FriendMessageEvent,MessageEvent
from .message import Message, MessageSegment
# from .log import log
import json
from pydantic import BaseModel
import base64
from pydantic import Field
from pathlib import Path

if TYPE_CHECKING:
    from .adapter import Adapter
from .utils import FileType, _resolve_data_type, get_image_size
from .models import (
    BaseResponse,
    Response,
    UploadImageVoiceResponse,
    SendMsgResponse,
    UploadForwardMsgResponse,
    GetGroupListResponse,
    GetGroupMemberListResponse,
    MemberLists
)
from nonebot.utils import logger_wrapper

from .log import log
from nonebot.log import logger



class Bot(BaseBot):
    """
    OPQ 协议 Bot 适配。
    """
    adapter: "Adapter"

    @override
    # def __init__(self, adapter: Adapter, self_id: str, **kwargs: Any):
    def __init__(self, adapter: "Adapter", self_id: str, **kwargs: Any):
        super().__init__(adapter, self_id)
        self.adapter = adapter
        self.http_url: str = self.adapter.http_url
        # 一些有关 Bot 的信息也可以在此定义和存储

    async def handle_event(self, event: Union[Event, MessageEvent]) -> None:
        """处理收到的事件。"""
        if isinstance(event, MessageEvent):
            sender_id = str(event.user_id)
            self_id = str(self.self_id)

            if sender_id == self_id:
                # 🐾 是 Bot 自己发的消息，直接忽略~
                logger.info(f"忽略了自己发的消息")
                return
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
        log("INFO", f"API请求数据: payload:[{payload}]")
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
                log("SUCCESS", f"API返回: {ret}")
            else:
                log("ERROR", f"API返回: {ret}")
            return resp_model.ResponseData
        except Exception as e:
            log("ERROR", f"{e} \r\n API返回：{ret}")
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

    async def send_poke(self, group_id: int, user_id: int):
        """
        戳一戳
        :param group_id: 群号(event.group_id)
        :param user_id: qq号(event.user_id)
        :return:
        """
        request = self.build_request({"GroupCode": group_id, "Uin": user_id}, cmd="SsoGroup.Op.Pat")
        res = await self.post(request)
        return res

    async def send_like(self, user_uid: str):
        """
        好友点赞
        :param user_uid: uid(event.Sender.user_uid)
        :return:
        """
        request = self.build_request({"Uid": user_uid}, cmd="SsoFriend.Op.Zan")
        res = await self.post(request)
        return res

    async def get_status(self) -> dict:
        """
        获取OPQ框架信息 (机器人在线列表等等)
        :return:
        """
        request = self.build_request({}, cmd="ClusterInfo")
        res = await self.post(request)
        return res

    async def get_group_member_list(self, group_id: int) -> List[MemberLists]:
        """
        获取群成员信息
        :param group_id: 群号(event.group_id)
        :return: List[MemberLists]
        """
        lastbuffer = "null"
        memberlist = []
        while lastbuffer:
            payload = {
                "GroupCode": group_id,
                "LastBuffer": lastbuffer if lastbuffer != "null" else None
            }
            request = self.build_request(payload, cmd="GetGroupMemberLists")
            res = await self.post(request)
            data = GetGroupMemberListResponse(**res)
            memberlist += data.MemberLists
            lastbuffer = data.LastBuffer

        return memberlist

    async def get_group_list(self) -> GetGroupListResponse:
        """
        获取群列表
        :return: GetGroupListResponse
        """
        request = self.build_request({}, cmd="GetGroupLists")
        res = await self.post(request)
        return GetGroupListResponse(**res)

    async def set_group_ban(
            self,
            group_id: int,
            user_uid: str,
            duration: int
    ):
        """
        禁言群组成员
        :param group_id: 群号 (event.group_id)
        :param user_uid: 成员uid(event.Sender.user_uid)
        :param duration: 禁言秒数 至少60秒 至多30天 禁言一天为24*3600=86400 参数为0解除禁言
        :return:
        """
        payload = {
            "OpCode": 4691,
            "GroupCode": group_id,
            "Uid": user_uid,
            "BanTime": duration
        }
        request = self.build_request(payload, cmd="SsoGroup.Op")
        res = await self.post(request)
        return res

    async def send_forward_msg(
            self,
            event: Event,
            messages: list[Union[Message, MessageSegment, str]]
    ):
        """
        发送合并转发消息,每条消息只支持一张图,多的图会自动拆分
        :param event: event对象
        :param messages: 需要组合的message(只支持text和image)
        :return: api返回的数据
        """
        if event.__type__ == EventType.GROUP_NEW_MSG:  # 群聊
            return await self.send_group_forward_msg(
                group_id=event.group_id,
                messages=messages
            )
        elif event.__type__ == EventType.FRIEND_NEW_MSG:  # 好友和私聊
            return await self.send_private_forward_msg(
                user_id=event.user_id,
                group_id=event.group_id,
                messages=messages
            )

    async def send_group_forward_msg(
            self,
            group_id: int,
            messages: list[Union[Message, MessageSegment, str]]
    ) -> SendMsgResponse:
        """
        发送群组的合并转发消息,每条消息只支持一张图,多的图会自动拆分
        :param messages: 需要组合的message(只支持text和image)
        :param group_id: 群号(event.group_id)
        :return: api返回的数据
        """
        json_msg = await self.build_forward_msg(messages)
        return await self.send_group_json_msg(group_id, json_msg)

    async def send_private_forward_msg(
            self,
            user_id: int,
            messages: list[Union[Message, MessageSegment, str]],
            group_id: Optional[int] = None
    ) -> SendMsgResponse:
        """
        发送好友或临时会话的合并转发消息,每条消息只支持一张图,多的图会自动拆分
        :param user_id: qq号(event.user_id)
        :param messages: 需要组合的message(只支持text和image)
        :param group_id: 群号(event.group_id)
        :return: api返回的数据
        """
        json_msg = await self.build_forward_msg(messages)
        return await self.send_private_json_msg(user_id, json_msg, group_id)

    async def send_group_json_msg(
            self,
            group_id: int,
            json_content: str
    ) -> SendMsgResponse:
        """
        发送群组的json消息
        :param group_id: 群号
        :param json_content: json文本(json.dumps({"data":"test"}))
        :return: api返回的数据
        """
        payload = {
            "ToUin": group_id,
            "ToType": 2,
            "SubMsgType": 51,
            "Content": json_content
        }

        request = self.build_request(payload)
        return await self.post(request)

    async def send_private_json_msg(
            self,
            user_id: int,
            json_content: str,
            group_id: Optional[int] = None
    ) -> SendMsgResponse:
        """
        发送好友或临时会话的json消息
        :param user_id: qq号(event.user_id)
        :param json_content: json文本(json.dumps({"data":"test"}))
        :param group_id: 群号
        :return: api返回的数据
        """
        payload = {
            "ToUin": user_id,
            "ToType": 3 if group_id else 1,
            "SubMsgType": 51,
            "Content": json_content
        }
        if group_id:
            payload["GroupCode"] = group_id
        request = self.build_request(payload)
        return await self.post(request)

    async def build_forward_msg(
            self,
            messages: list[Union[Message, MessageSegment, str]],
    ) -> str:
        """
        生成合并转发消息
        :param messages: message对象(只支持text和image)
        :return: 生成好的json模板
        """
        json_template = {"app": "com.tencent.multimsg",
                         "config": {"autosize": 1, "forward": 1, "round": 1, "type": "normal", "width": 300},
                         "desc": "[聊天记录]",
                         "meta": {
                             "detail":
                                 {
                                     "news": [
                                         {"text": "概要1"}, {"text": "概要2"}
                                     ],
                                     "resid": "7G6x5GJk07ze2AAjirAywSEYLRqVRj1sU0Pxv9mfmhe/YYqFV2kreIxtoqH+flEV",
                                     "source": "QQ用户的聊天记录",
                                     "summary": "查看4条转发消息",
                                     "uniseq": "dcdd7729-7482-4e1a-acd8-1777a314af0f"
                                 }
                         },
                         "prompt": "[聊天记录]", "ver": "0.0.0.5",
                         "view": "contact"}
        msg_bodys = []
        news = []
        for message in messages:
            data = await self._message_to_protocol_data(EventType.GROUP_NEW_MSG, message)
            if images := data.get("Images"):
                msg_bodys.append(
                    {
                        "Content": data.get("Content"),
                        "Image": data.get("Images")[0]
                    },
                )
                if text := data.get("Content"):
                    news.append({"text": f"QQ用户: {text}[图片]"})
                else:
                    news.append({"text": "QQ用户: [图片]"})
                for image in images[1:]:
                    msg_bodys.append(
                        {
                            "Image": image
                        },
                    )
                    news.append({"text": "QQ用户: [图片]"})
            else:
                if text := data.get("Content"):
                    msg_bodys.append(
                        {
                            "Content": text
                        }
                    )
                    news.append({"text": f"QQ用户: {text}"})
        json_template["meta"]["detail"]["news"] = news[:4]
        json_template["meta"]["detail"]["summary"] = f"查看{len(msg_bodys)}条转发消息"

        payload = {
                      "ToUin": self.self_id,
                      "ToType": 1,
                  } | {"MsgBodys": msg_bodys}

        request = self.build_request(payload, cmd="SsoUploadMultiMsg")
        res = UploadForwardMsgResponse(**await self.post(request))
        json_template["meta"]["detail"]["resid"] = res.ResId
        return json.dumps(json_template)

    async def download_to_bytes(self, url: str) -> bytes:
        """下载文件返回bytes"""
        req = Request(
            method="GET",
            url=url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"},
            timeout=15
        )
        res = await self.adapter.request(req)
        return res.content

    async def get_group_file_url(
            self,
            group_id: int,
            fileid: str
    ):
        """
        获取群文件的下载链接
        :param group_id: 群号
        :param fileid: file类型message的fileid
        :return:
        """
        request = self.build_request(
            {
                "OpCode": 1750,
                "ToUin": group_id,
                "FileId": fileid
            },
            cmd="SsoGroup.File"
        )
        res = await self.post(request)
        return res

    async def upload_group_file(
            self,
            group_id: int,
            filename: str,
            file: Union[str, Path, BytesIO, bytes],
            notify: bool = True,
    ):
        """
        上传群文件
        :param group_id: 群号(event.group_id)
        :param filename: 文件名
        :param file: 文件
        :param notify: 推送通知
        :return:
        """
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
        """
        上传图片或语音资源文件
        :param command_id: 1好友图片 2群组图片 26好友语音 29群组语音
        :param file: 资源文件
        :return: api返回的数据
        """
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
        """
        发送群组消息
        :param message: message对象
        :param group_id: 群号(event.group_id)
        :return: api返回的数据
        """
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
        """
        发送好友消息与临时会话消息
        :param user_id: qq号(event.user_id)
        :param message: message对象
        :param group_id: 群号(event.group_id)
        :return: api返回的数据
        """
        data = await self._message_to_protocol_data(EventType.GROUP_NEW_MSG, message)
        payload = {
                      "ToUin": user_id,
                      "ToType": 3 if group_id else 1
                  } | data
        if group_id:
            payload["GroupCode"] = group_id
        request = self.build_request(payload)
        return await self.post(request)

    async def revoke_group_msg(
            self,
            group_id: int,
            msg_seq: int,
            msg_random: int
    ) -> Optional[SendMsgResponse]:
        """
        撤回群消息
        :param group_id: group_id
        :param msg_seq: msg_seq
        :param msg_random: msg_random
        :return: api返回的数据
        """
        payload = {
            "GroupCode": group_id,
            "MsgSeq": msg_seq,
            "MsgRandom": msg_random
        }
        request = self.build_request(payload, cmd="GroupRevokeMsg")
        return await self.post(request)

    async def _message_to_protocol_data(
        self,
        event_type: EventType,
        message: Union[str, Message, MessageSegment]
    ) -> dict:
        """
        将 Message 对象转换成 OPQ 协议所需数据
        """
        message = Message(message)  # 确保是 Message 对象
        Content = ""
        images = []
        at_uin_lists = []

        for segment in message:
            if segment.type == "text":
                Content += segment.data.get("text", "")
            elif segment.type == "image":
                if all(segment.data.get(key) for key in ["FileId", "FileMd5", "FileSize"]):
                    images.append({
                        "FileId": segment.data["FileId"],
                        "FileMd5": segment.data["FileMd5"],
                        "FileSize": segment.data["FileSize"],
                        "Height": segment.data.get("Height"),
                        "Width": segment.data.get("Width")
                    })
                else:
                    img = await self.upload_image_voice(
                        2 if event_type == EventType.GROUP_NEW_MSG else 1,
                        file=segment.data.get("file")
                    )
                    images.append({
                        "FileId": img.FileId,
                        "FileMd5": img.FileMd5,
                        "FileSize": img.FileSize,
                        "Height": img.Height,
                        "Width": img.Width,
                    })
            elif segment.type == "at":
                uin = segment.data.get("uin")
                if uin:
                    at_uin_lists.append({"Uin": uin})
                    Content += f"@{uin} "
            elif segment.type == "atall":
                at_uin_lists.append({"Uin": 0})
                Content += "@全体成员 "

        payload = {
            "Content": Content or None,
            "AtUinLists": at_uin_lists or None,
            "Images": images or None,
        }
        return payload



    @override
    async def send(
            self,
            event: Event,
            message: Union[str, Message, MessageSegment],
            **kwargs: Any,
    ):
        """
        发送消息
        :param event: event对象
        :param message: message对象
        :return: api返回数据
        """
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
        """
        回复消息
        :param event: event对象(只能在好友和群聊回复,不支持临时会话)
        :param message: message对象
        :return: api返回数据
        """
        if event.message_type == "private":
            raise ValueError(f"unsupported message_type: private")
        else:
            data = await self._message_to_protocol_data(event.__type__, message)
            payload = {
                          "ToUin": event.group_id if event.message_type == "group" else event.user_id,
                          "ToType": 2 if event.message_type == "group" else 1,
                          "ReplyTo": {
                              "MsgSeq": event.message_id.seq,
                              "MsgTime": event.message_id.time,
                              "MsgUid": event.message_id.uid
                          },
                      } | data
            request = self.build_request(payload)
            return await self.post(request)
