"""Recover durable tool intents without replaying uncertain side effects."""
import json
from mvvm.models.chat_models import Message, ToolUsePart, ToolResultPart


def close_pending_tools(session):
    recovered = []
    changed = False
    messages = session.messages
    index = 0
    while index < len(messages):
        message = messages[index]
        recovered.append(message)
        calls = [p for p in message.content if isinstance(p, ToolUsePart)] if isinstance(message.content, list) else []
        if message.role == 'assistant' and calls:
            end = index + 1
            results = set()
            while end < len(messages):
                parts = messages[end].content
                if not isinstance(parts, list) or not parts or not all(isinstance(p, ToolResultPart) for p in parts):
                    break
                recovered.append(messages[end])
                results.update(p.toolUseId for p in parts)
                end += 1
            missing = [c for c in calls if c.id not in results]
            if missing:
                recovered.append(Message(role='user', content=[ToolResultPart(toolUseId=c.id, isError=True, content=json.dumps({
                    'status':'interrupted_unknown', 'executed':'unknown', 'retry':False,
                    'reason':'中断时结果未知，未自动重试；先核对实际状态再决定新操作'
                }, ensure_ascii=False)) for c in missing]))
                changed = True
            index = end
        else:
            index += 1
    if changed:
        session.messages = recovered
    return changed
