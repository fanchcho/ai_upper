"""Recover durable tool intents without replaying uncertain side effects."""
import json
from mvvm.models.chat_models import Message, ToolUsePart, ToolResultPart


def close_pending_tools(session, checkpoint=None, resume=None):
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
                parts = []
                for call in missing:
                    saved = checkpoint.result(session.id, call.id) if checkpoint else None
                    if saved is None and resume is not None:
                        saved = resume(call)
                    if saved is not None:
                        parts.append(ToolResultPart(toolUseId=call.id, isError=saved.is_error, content=saved.content, images=saved.images))
                        if saved.delivered:
                            from mvvm.services.deliverables import record_delivered
                            session.delivered = record_delivered(session.delivered, call.id, saved)
                    else:
                        parts.append(ToolResultPart(toolUseId=call.id, isError=True, content=json.dumps({
                            'status':'interrupted_unknown', 'executed':'unknown', 'retry':False,
                            'reason':'中断时结果未知，未自动重试；先核对实际状态再决定新操作'
                        }, ensure_ascii=False)))
                recovered.append(Message(role='user', content=parts))
                changed = True
            index = end
        else:
            index += 1
    if changed:
        session.messages = recovered
    return changed
