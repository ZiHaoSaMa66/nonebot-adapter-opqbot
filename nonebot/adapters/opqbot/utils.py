import asyncio
import base64
import functools
import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, List, Tuple, Union
from PIL import Image

from enum import Enum

_T_Data = Union[str, bytes, BytesIO, BinaryIO, Path, List[str]]

_BASE64_REGEX = re.compile(
    r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)$"
)


class FileType(Enum):
    TYPE_AUTO: int = 0
    TYPE_URL: int = 1
    TYPE_BASE64: int = 2
    TYPE_MD5: int = 3
    TYPE_PATH: int = 4


def _resolve_data_type(data: _T_Data) -> Tuple[FileType, _T_Data]:
    """用来处理数据类型，必要时需要对数据进行进一步加工再返回"""
    # FIXME: if hell. 逻辑并不严谨
    # url, path, md5, base64
    # url
    #   http:// 或 https:// 开头的肯定是
    # path
    #   1. Path => 确定
    #   2. str => 用常规经验判断
    #       a. 本地路径一般不可能超过 1000 吧
    #       b. 文件存在
    # md5
    #   1. List[str] => 确定
    #   2. str 目前来看，opq收到的图片MD5均是长度为24，==结尾，
    #   语音并不支持md5发送, 基本可以确定, 并且一张图片的base64不可能这么短

    # base64
    #   1. 前面都不符合剩余的情况就是base64
    #   2. bytes 一定是base64
    #   3. base64:// 开头

    # Path, List[str]

    type = None

    if isinstance(data, Path):  # Path 特殊对象优先判断
        type = FileType.TYPE_PATH
        data = str(data.absolute())
        # data = "/root/1.txt"
    elif isinstance(data, bytes):  # bytes 必定是base64
        type = FileType.TYPE_BASE64
        data = base64.b64encode(data).decode()
    elif isinstance(data, BytesIO):
        type = FileType.TYPE_BASE64
        data = base64.b64encode(data.getvalue()).decode()
    elif isinstance(data, BinaryIO):
        type = FileType.TYPE_BASE64
        data = base64.b64encode(data.read()).decode()
    elif isinstance(data, list):  # 必定为MD5
        type = FileType.TYPE_MD5
    # 处理 str
    elif data.startswith("http://") or data.startswith("https://"):
        type = FileType.TYPE_URL
    elif data.startswith("base64://"):
        type = FileType.TYPE_BASE64
        data = data[9:]
    elif len(data) == 24 and data.endswith("=="):
        type = FileType.TYPE_MD5
    elif len(data) < 1000:
        if Path(data).exists():
            type = FileType.TYPE_PATH
        elif re.match(_BASE64_REGEX, data):
            type = FileType.TYPE_BASE64
        # else:
        #     return cls.TYPE_MD5
    elif re.match(_BASE64_REGEX, data):
        type = FileType.TYPE_BASE64

    if type is not None:
        return type, data

    assert False, "正常情况下这里应该是执行不到的"


def get_image_size(data: Union[bytes, BytesIO, str, Path]) -> Tuple[int, int]:
    """获取图像尺寸
    :param data: 目标图像。接收图像路径或图像二进制数据
    :return: (长, 宽)
    """
    d_type, data = _resolve_data_type(data)
    if d_type == FileType.TYPE_URL:
        raise "不能是url"
    elif d_type == FileType.TYPE_BASE64:
        image = Image.open(BytesIO(base64.b64decode(data)))
    elif d_type == FileType.TYPE_PATH:
        image = Image.open(data.absolute() if isinstance(data, Path) else data)
    else:
        raise TypeError("参数类型有误")
    width, height = image.size
    return height, width
