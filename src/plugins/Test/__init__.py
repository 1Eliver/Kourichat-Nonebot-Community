import html
import re
from typing import Optional
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Event
from nonebot.rule import to_me

test = on_message(rule=to_me(), priority=10)

@test.handle()
# 测试消息类型
async def handle_message(event: Event):
    if event.get_user_id() == "2247335689":
        # 获取消息对象
        message = event.get_message()
        
        # 获取消息类型
        msg_type = "未知类型"
        for seg in message:
            msg_type = f"消息类型: {seg.type}"
            await test.send(f"seg内容: {seg}")
            if seg.type == "image":
                await test.send(f"seg内容: {seg.data['url']}")
            if seg.type == "face":
                await test.send(f"seg内容: {await _decode_face(str(seg.data['raw']))}")
            break  # 获取第一个片段的类型
        
        # 显示消息类型
        await test.send(msg_type)
        
        # 显示完整消息
        await test.send(f"完整消息: {message}")
        
        # 如果是纯文本，还可以显示纯文本内容
        plain_text = message.extract_plain_text()
        if plain_text:
            await test.finish(f"纯文本内容: {plain_text}")
        else:
            await test.finish("该消息不包含纯文本内容")

    #  这里知道一件事，消息可能是多段组成的
    #     msg = Message([
    #     MessageSegment.text("这是一张图片："),
    #     MessageSegment.image("https://example.com/image.jpg")
    # ])
    # 我们的要处理的消息不是Message，而是MessageSegment
    # 所以我们要遍历处理MessageSegment
    
async def _decode_face(face_raw_content: str) -> Optional[str | None]:
        html_part = re.search(r"'faceText': '(.*?)'", face_raw_content).group(1)
        decoded_text = html.unescape(html_part)
        if decoded_text.startswith('[') and decoded_text.endswith(']'):
            chinese_text = decoded_text[1:-1]
            return chinese_text
        else:
            return None
