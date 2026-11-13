"""会话持久化：一对话一文件 + 轻量索引。

移植自 Deva `apps/desktop/src/main/services/chat-store.ts`，落盘格式逐字段一致：

    <home>/data/chats/<id>.json            单条对话（正文）
    <home>/data/chats/_index.json          仅元信息，供列表 O(1) 读取
    <home>/data/chats/<id>.compacted-*.jsonl   已压缩掉的早期消息段（一行一条）

为什么保持这个格式而不是换 JSONL/SQLite：迁移期间要和 Deva 用同一个 `DEVA_HOME`
互相读写，格式一变就得写双份解析与迁移脚本，而且历史文件里的 `bucket`、`notices`
等边车字段只有原样保留才对得上。索引是**派生数据**：缺失或损坏时扫描 `*.json`
重建（Deva 修过的老 bug，这里不退回只读索引）。

与 Deva 的一处刻意差异：单条对话落盘失败**不再静默**。Deva 的 save() 把异常
吞掉只留内存态，用户以为存下了；这里让异常抛出去，由 ViewModel 转成界面错误。
索引落盘失败仍然静默——索引可从对话文件重建，吞掉是安全的。
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import string
import time
from pathlib import Path
from typing import Optional

from mvvm.models.chat_models import (
    ChatSessionMeta,
    CompactedRef,
    Message,
    StoredSession,
)
from mvvm.services.model_view import model_first

INDEX_FILE = "_index.json"
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def derive_title(text: str) -> str:
    """首条用户消息 → 会话标题（Deva `deriveTitle`：压空白、30 字符截断加省略号）。"""
    one_line = " ".join(text.split())
    if not one_line:
        return ""
    return one_line[:30] + "…" if len(one_line) > 30 else one_line


def safe_id(session_id: str) -> str:
    """会话 id → 文件名安全形式（白名单字符），杜绝 `../` 与分隔符造成的路径穿越。"""
    cleaned = _SAFE_ID.sub("", session_id)
    if not cleaned:
        raise ValueError(f"非法会话 id：{session_id!r}")
    return cleaned


def write_file_atomic(path: Path, data: str) -> None:
    """先写 `.tmp` 再 rename；rename 失败（跨设备/占位）回退直接覆盖。"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(data, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


def base36(value: float) -> str:
    """整数 → 36 进制（Deva 用 `Date.now().toString(36)` 给拆分文件名打时间戳）。"""
    number = int(value)
    if number <= 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out: list[str] = []
    while number:
        number, rem = divmod(number, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


class ChatSessionStore:
    """对话文件的读写。不含 Qt、不认识 ViewModel，可在纯 Python 下测试。"""

    def __init__(self, home: Optional[Path | str] = None) -> None:
        self._home = Path(home) if home is not None else self._default_home()
        self._chats_dir = self._home / "data" / "chats"
        self._cache: dict[str, StoredSession] = {}
        self._index: Optional[dict[str, ChatSessionMeta]] = None
        # 已写进拆分文件的那段消息（对象引用）：保存时逐个比对，前缀原样还在就只追加新的，
        # 否则换新文件重写（Deva 用 WeakMap<StoredSession, Message[]>，这里按会话 id 存）。
        self._persisted_prefix: dict[str, list[Message]] = {}

    @staticmethod
    def _default_home() -> Path:
        """与 Deva 的 `getDevaHome()` 同口径：`DEVA_HOME` 优先，缺省 `~/.deva`。"""
        override = os.environ.get("DEVA_HOME")
        return Path(override) if override else Path.home() / ".deva"

    # ── 路径 ──────────────────────────────────────────────────────────────
    @property
    def home(self) -> Path:
        """数据根目录（`<home>/data/chats` 的父级）。"""
        return self._home

    @property
    def chats_dir(self) -> Path:
        self._chats_dir.mkdir(parents=True, exist_ok=True)
        return self._chats_dir

    def session_path(self, session_id: str) -> Path:
        return self.chats_dir / f"{safe_id(session_id)}.json"

    def index_path(self) -> Path:
        return self.chats_dir / INDEX_FILE

    # ── 索引 ──────────────────────────────────────────────────────────────
    def _ensure_index(self) -> dict[str, ChatSessionMeta]:
        """读索引；缺失/损坏则扫描对话文件重建（自愈）。"""
        if self._index is not None:
            return self._index
        index: dict[str, ChatSessionMeta] = {}
        try:
            parsed = json.loads(self.index_path().read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        meta = ChatSessionMeta.model_validate(item)
                        index[meta.id] = meta
                self._index = index
                return index
        except (OSError, ValueError, TypeError):
            pass  # 无索引 / 解析失败 → 扫描重建

        try:
            for path in sorted(self._chats_dir.glob("*.json")):
                if path.name == INDEX_FILE:
                    continue
                try:
                    session = StoredSession.model_validate_json(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue  # 跳过坏文件：一个文件坏掉不该让整个列表打不开
                index[session.id] = session.meta()
        except OSError:
            pass
        self._index = index
        self._persist_index()
        return index

    def _persist_index(self) -> None:
        """索引落盘失败静默：它可从对话文件重建，吞掉是安全的。"""
        if self._index is None:
            return
        payload = [m.model_dump(mode="json", exclude_none=True) for m in self._index.values()]
        try:
            write_file_atomic(self.index_path(), json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError:
            pass

    # ── 读 ────────────────────────────────────────────────────────────────
    def load_session(self, session_id: str) -> Optional[StoredSession]:
        """载入一条对话（缓存优先）。拆分存盘的会话在内存里拼回完整记录。"""
        session_id = safe_id(session_id)
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached
        path = self.session_path(session_id)
        try:
            session = StoredSession.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        tidy = self._restore_compacted(session)
        self._cache[session.id] = session
        if tidy != "keep":
            # 主文件不引用的拆分文件（换文件后没删掉的旧文件、写到一半崩溃的新文件）顺手清掉。
            self._remove_compacted_files(session.id, keep=tidy)
        return session

    def _restore_compacted(self, session: StoredSession) -> Optional[str]:
        """把 `.jsonl` 里的早期消息段拼回 messages 前面。

        返回主文件不引用的拆分文件名（调用方在主文件之外顺手清掉）；读不出较早记录时返回
        `"keep"`，表示**不要**清理——文件可能只是暂时被占用，留着下次还能读回来。
        """
        if session.compacted is None:
            return None
        keep_file = session.compacted.file
        older = self._read_compacted(session.compacted.count, keep_file)
        if older is not None:
            session.messages = older + session.messages
            self._persisted_prefix[session.id] = list(older)
            session.compacted = None
            return None
        # 拆分文件缺失/损坏：只剩主文件里的部分（模型看到的内容完整，丢的是更早的显示记录）。
        # 提示锚点按完整记录记的，整体前移；下次保存重新判断要不要拆分。
        n = session.compacted.count
        if session.notices:
            session.notices = [
                n_.model_copy(update={"after": n_.after - n})
                for n_ in session.notices
                if n_.after >= n
            ]
        session.compacted = None
        return "keep"

    def _read_compacted(self, count: int, filename: str) -> Optional[list[Message]]:
        try:
            text = (self.chats_dir / filename).read_text(encoding="utf-8")
        except OSError:
            return None
        out: list[Message] = []
        for line in text.splitlines():
            if len(out) >= count:
                break
            if not line.strip():
                continue
            try:
                out.append(Message.model_validate_json(line))
            except ValueError:
                return None
        return out if len(out) == count else None

    def list_sessions(self) -> list[ChatSessionMeta]:
        """全部会话（按 updatedAt 倒序；会话无「分桶」，一次列全部）。"""
        return sorted(self._ensure_index().values(), key=lambda m: m.updatedAt, reverse=True)

    # ── 写 ────────────────────────────────────────────────────────────────
    def ensure_session(
        self,
        session_id: str,
        *,
        persona_id: Optional[str] = None,
        focus_root: Optional[str] = None,
        model: Optional[str] = None,
    ) -> StoredSession:
        """取会话；不存在则新建（只进内存与索引，首次 save 才落盘——与 Deva 一致）。

        已存在的会话：personaId 只补不覆盖（一次性绑定），focusRoot/model 显式提供即覆盖。
        """
        session_id = safe_id(session_id)
        session = self.load_session(session_id)
        if session is None:
            session = StoredSession(id=session_id)
            session.personaId = persona_id
            session.focusRoot = focus_root
            session.model = model
            self._cache[session_id] = session
            self._ensure_index()[session_id] = session.meta()
            return session
        if session.personaId is None and persona_id is not None:
            session.personaId = persona_id
        if focus_root is not None:
            session.focusRoot = focus_root
        if model is not None:
            session.model = model
        return session

    def append_message(self, session_id: str, message: Message, *, save: bool = True) -> StoredSession:
        """追加一条消息；默认立即落盘（用户要的「追加消息 → 重启读回」）。"""
        session = self.ensure_session(session_id)
        session.messages.append(message)
        session.touch()
        if not session.title:
            title = self._title_from(session)
            if title:
                session.title = title
        if save:
            self.save(session_id)
        return session

    @staticmethod
    def _title_from(session: StoredSession) -> str:
        for message in session.messages:
            if message.role == "user":
                return derive_title(message.text())
        return ""

    def save(self, session_id: str) -> None:
        """写该对话文件 + 刷新索引。只重写这一条，与其它对话无关。

        压缩过的对话只重写模型还看得到的那部分，更早的追加进拆分文件（见 `_sync_compacted`）。
        """
        session_id = safe_id(session_id)
        session = self._cache.get(session_id)
        if session is None:
            raise KeyError(f"会话不在内存中，未加载过：{session_id}")
        stale = self._sync_compacted(session)
        live = session.messages[session.compacted.count:] if session.compacted else session.messages
        payload = session.model_copy(update={"messages": live})
        # 先写主文件：拆分文件在 _sync_compacted 里已经先落盘（崩溃安全：主文件记的条数只会少于
        # 拆分文件的行数，载入时多出的行被忽略；换新文件后崩溃，主文件仍指向旧文件）。
        write_file_atomic(
            self.session_path(session_id),
            payload.model_dump_json(indent=2, exclude_none=True),
        )
        if stale:
            self._remove_compacted_files(session_id, keep=session.compacted.file if session.compacted else None)
        self._ensure_index()[session_id] = session.meta()
        self._persist_index()

    # ── 拆分存盘（见 StoredSession.compacted）──────────────────────────────
    def _compacted_file(self, session_id: str) -> str:
        """拆分文件名：`<id>.compacted-<时间36><随机>.jsonl`。不以 .json 结尾，扫描重建索引时天然被排除。"""
        suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=4)
        )
        return f"{safe_id(session_id)}.compacted-{base36(time.time() * 1000)}{suffix}.jsonl"

    def _to_lines(self, messages: list[Message]) -> str:
        return "".join(
            message.model_dump_json(exclude_none=True) + "\n" for message in messages
        )

    def _remove_compacted_files(self, session_id: str, keep: Optional[str] = None) -> None:
        """删掉该对话除 keep 以外的拆分文件（换文件后的旧文件、崩溃留下的半截新文件）。"""
        prefix = f"{safe_id(session_id)}.compacted-"
        try:
            for path in self.chats_dir.iterdir():
                if path.name.startswith(prefix) and path.name != keep:
                    path.unlink(missing_ok=True)
        except OSError:
            pass  # 清理失败无害：下次载入再清

    def _sync_compacted(self, session: StoredSession) -> Optional[str]:
        """让拆分文件恰好存着 messages 里模型已看不到的那段，并更新 session.compacted。

        返回写完主文件后要删的旧拆分文件名。与 Deva `syncCompacted` 同算法：
        - 上一次拆分的前缀对象引用原样还在、且切点只会前移，就只**追加**新压掉的那几条；
        - 否则（首次压缩 / 删了轮 / 回滚 / 修补改到这段 / 换了进程）整份换新文件重写。
          文件名带随机后缀，同一毫秒里连着换两次也不会与旧文件同名。
        """
        cut = model_first(session.messages)
        prev = session.compacted
        if cut == 0:
            # 没压缩过 / 回滚、删轮回到了第一次压缩之前：不拆分，旧文件在主文件写好后删。
            self._persisted_prefix.pop(session.id, None)
            session.compacted = None
            return prev.file if prev else None

        saved = self._persisted_prefix.get(session.id)
        intact = (
            prev is not None
            and saved is not None
            and len(saved) == prev.count
            and len(saved) <= cut
        )
        if intact:
            for index in range(len(saved)):
                if session.messages[index] is not saved[index]:
                    intact = False
                    break
        if intact and prev is not None:
            if cut > prev.count:
                with (self.chats_dir / prev.file).open("a", encoding="utf-8") as handle:
                    handle.write(self._to_lines(session.messages[prev.count:cut]))
            session.compacted = CompactedRef(count=cut, file=prev.file)
            self._persisted_prefix[session.id] = list(session.messages[:cut])
            return None

        filename = self._compacted_file(session.id)
        write_file_atomic(self.chats_dir / filename, self._to_lines(session.messages[:cut]))
        session.compacted = CompactedRef(count=cut, file=filename)
        self._persisted_prefix[session.id] = list(session.messages[:cut])
        return prev.file if prev else None

    def _remember_loaded_prefix(self, session_id: str, prefix: list[Message]) -> None:
        """载入时记下拆分段的对象引用：下次保存据此判断「前缀是否原样还在」。"""
        self._persisted_prefix[session_id] = prefix

    def rename_session(self, session_id: str, title: str) -> ChatSessionMeta:
        """只改标题与索引，不动 updatedAt（Deva 的列表排序语义：重命名不该把会话顶到最前）。"""
        session = self.ensure_session(session_id)
        session.title = title
        self.save(session_id)
        return self._ensure_index()[session.id]

    def set_archived(self, session_id: str, archived: bool) -> ChatSessionMeta:
        session = self.ensure_session(session_id)
        session.archived = archived
        self.save(session_id)
        return self._ensure_index()[session.id]

    def delete_session(self, session_id: str) -> bool:
        """删除对话文件与其拆分文件；不存在返回 False。"""
        session_id = safe_id(session_id)
        path = self.session_path(session_id)
        existed = path.exists()
        self._cache.pop(session_id, None)
        self._persisted_prefix.pop(session_id, None)
        for chunk in self.chats_dir.glob(f"{session_id}.compacted-*.jsonl"):
            chunk.unlink(missing_ok=True)
        if path.exists():
            path.unlink()
        index = self._ensure_index()
        index.pop(session_id, None)
        self._persist_index()
        return existed

    def copy_session_file(self, session_id: str, destination: Path) -> Path:
        """把一条对话的原始 JSON 复制出去（备份/导出用，不改动原文件）。"""
        destination.write_bytes(self.session_path(session_id).read_bytes())
        return destination

    # ── 展示辅助 ──────────────────────────────────────────────────────────
    def visible_sessions(self) -> list[ChatSessionMeta]:
        """左侧列表：隐藏归档项、成员会话，以及**尚未落盘的惰性会话**（Deva 的列表口径）。

        惰性会话只活在内存索引里（`ensure_session` 不写盘）：Deva 的渲染层新建后只
        `setCurrent(id)`，主进程索引里根本没有它；本工程 `open_session` 直接调
        `ensure_session`，所以要在投影时按「文件是否存在」把它排除，等价于 Deva 的
        「未 `createSession` 不列出」。首条消息落盘后文件出现，会话自然进列表。
        """
        return [
            m
            for m in self.list_sessions()
            if not m.archived and not m.parentId and self.session_path(m.id).exists()
        ]

    def cleanup(self) -> None:
        """测试/退出用：清内存缓存（不删文件）。"""
        self._cache.clear()
        self._persisted_prefix.clear()
        self._index = None


def clone_store_for_tests(source: ChatSessionStore, target_home: Path) -> ChatSessionStore:
    """把 source 的整个 chats 目录复制到 target_home（模拟「重装/换机后读回」）。

    生产代码不用它；测试里用它把「重启」这件事做成真的换目录，而不是清缓存假装。
    """
    target = ChatSessionStore(target_home)
    src_dir = source.chats_dir
    dst_dir = target.chats_dir
    for item in src_dir.iterdir():
        if item.is_file() and item.name != INDEX_FILE:
            shutil.copy2(item, dst_dir / item.name)
    return target


__all__ = [
    "ChatSessionStore",
    "INDEX_FILE",
    "base36",
    "clone_store_for_tests",
    "derive_title",
    "safe_id",
    "write_file_atomic",
]
