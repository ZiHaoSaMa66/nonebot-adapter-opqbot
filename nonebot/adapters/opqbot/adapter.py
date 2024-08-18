import asyncio
from typing import Any, Optional, Dict, List, Callable
from typing_extensions import override
from .log import log
from nonebot import get_plugin_config
from nonebot.exception import WebSocketClosed
from nonebot.utils import DataclassEncoder, escape_tag
from nonebot.compat import type_validate_python, type_validate_json
from nonebot.drivers import (
    URL,
    Driver,
    Request,
    Response,
    WebSocket,
    ForwardDriver,
    ReverseDriver,
    HTTPServerSetup,
    WebSocketServerSetup,
    WebSocketClientMixin,
    HTTPClientMixin
)

from nonebot.adapters import Adapter as BaseAdapter
import json
from .bot import Bot
from .event import Event, EVENT_CLASSES, EventType
from .config import Config
from .message import Message, MessageSegment


class Adapter(BaseAdapter):

    @override
    def __init__(self, driver: Driver, **kwargs: Any):
        super().__init__(driver, **kwargs)
        self.adapter_config = get_plugin_config(Config)
        self.task: Optional[asyncio.Task] = None  # 存储 ws 任务
        self.ws_url = f"ws://{self.adapter_config.url}/ws"
        self.http_url: str = f"http://{self.adapter_config.url}"
        self.bot_ids: list[int] = self.adapter_config.bots

        self.setup()

    @classmethod
    @override
    def get_name(cls) -> str:
        return "OPQ"

    @override
    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:
        log("DEBUG", f"Bot {bot.self_id} calling API <y>{api}</y>")
        api_handler: Optional[Callable[..., Any]] = getattr(bot.__class__, api, None)
        if api_handler is None:
            raise "无API"
        return await api_handler(bot, **data)

    def setup(self) -> None:
        if not isinstance(self.driver, HTTPClientMixin):
            raise RuntimeError(
                f"Current driver {self.config.driver} does not support "
                "http client requests! "
                "OPQBot Adapter need a HTTPClient Driver to work."
            )
        if not isinstance(self.driver, WebSocketClientMixin):
            raise RuntimeError(
                f"Current driver {self.config.driver} does not support "
                "websocket client! "
                "OPQBot Adapter need a WebSocketClient Driver to work."
            )
        # 在 NoneBot 启动和关闭时进行相关操作
        self.driver.on_startup(self.startup)
        self.driver.on_shutdown(self.shutdown)

    @classmethod
    def payload_to_event(cls, payload: Dict[str, Any]) -> Optional[Event]:
        """根据平台事件的特性，转换平台 payload 为具体 Event

        Event 模型继承自 pydantic.BaseModel，具体请参考 pydantic 文档
        """

        # 做一层异常处理，以应对平台事件数据的变更
        try:
            event_name = payload.get('CurrentPacket').get('EventName', None)
            event_model = EVENT_CLASSES.get(event_name, None)
            event = type_validate_python(event_model, payload)
            if event.get_type() == "message":  # message消息无MsgBody就跳过
                if not event.CurrentPacket.EventData.MsgBody:
                    return
            return event
        except Exception as e:
            # 无法正常解析为具体 Event 时，给出日志提示
            log(
                "WARNING",
                f"Parse event error: {str(payload)}",
            )
            print(e)
            # 也可以尝试转为基础 Event 进行处理
            return
            # return type_validate_python(Event, payload)

    async def _forward_ws(self):
        request = Request(
            method="GET",
            url=self.ws_url,
        )
        for bot_id in self.bot_ids:
            bot = Bot(self, self_id=str(bot_id))
            self.bot_connect(bot)
        while True:
            try:
                log("INFO", f"Attempting to connect to server at {self.ws_url}")
                async with self.websocket(request) as ws:
                    log("SUCCESS", f"Successfully connected to server at {self.ws_url}")
                    try:
                        while True:
                            payload: str = await ws.receive()
                            log("INFO", payload)
                            if not payload:
                                continue
                            if event := self.payload_to_event(json.loads(payload)):
                                if event.CurrentQQ not in self.bot_ids:
                                    return

                                    # bots[event.CurrentQQ] = bot  # 保存所有bot对象
                                # bot
                                task = self.bots[str(event.CurrentQQ)].handle_event(event)
                                asyncio.create_task(task)
                    except WebSocketClosed as e:
                        log(
                            "ERROR",
                            "<r><bg #f8bbd0>WebSocket Closed</bg #f8bbd0></r>",
                            e,
                        )
                    except Exception as e:
                        log(
                            "ERROR",
                            "<r><bg #f8bbd0>Error while process data from "
                            "websocket platform_websocket_url. "
                            "Trying to reconnect...</bg #f8bbd0></r>",
                            e,
                        )
                    finally:
                        # 这里要断开 Bot 连接
                        bots = self.bots.copy()
                        for bot in bots.values():
                            self.bot_disconnect(bot)
            except Exception as e:
                # 尝试重连
                log(
                    "ERROR",
                    "<r><bg #f8bbd0>Error while setup websocket to "
                    "platform_websocket_url. Trying to reconnect...</bg #f8bbd0></r>",
                    e,
                )
                await asyncio.sleep(3)  # 重连间隔

    async def startup(self) -> None:
        """定义启动时的操作，例如和平台建立连接"""
        self.task = asyncio.create_task(self._forward_ws())  # 建立 ws 连接

    async def shutdown(self) -> None:
        """定义关闭时的操作，例如停止任务、断开连接"""

        # 断开 ws 连接
        if self.task is not None and not self.task.done():
            self.task.cancel()
