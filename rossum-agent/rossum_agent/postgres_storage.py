"""PostgreSQL-based chat persistence using SQLAlchemy Core API."""

from __future__ import annotations

import datetime as dt
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, insert
from sqlalchemy.dialects.postgresql import array as pg_array

from rossum_agent.storage import ChatData, ChatMetadata, _build_chat_list_item, _preview_from_first_msg

if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


sa_metadata = sa.MetaData()

chats_table = sa.Table(
    "chats",
    sa_metadata,
    sa.Column("user_id", sa.Text, nullable=False, server_default=""),
    sa.Column("chat_id", sa.Text, nullable=False),
    sa.Column("messages", JSONB, nullable=False, server_default="[]"),
    sa.Column("output_dir", sa.Text, nullable=True),
    sa.Column("metadata_", JSONB, nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("user_id", "chat_id"),
    sa.Index("idx_chats_expires_at", "expires_at"),
)

chat_files_table = sa.Table(
    "chat_files",
    sa_metadata,
    sa.Column("chat_id", sa.Text, nullable=False),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("size", sa.Integer, nullable=False),
    sa.Column("content", BYTEA, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("chat_id", "filename"),
    sa.Index("idx_chat_files_expires_at", "expires_at"),
)


class PostgresStorage:
    """PostgreSQL storage for chat conversations.

    Follows the DAO pattern with SQLAlchemy Core API for type-safe queries.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        dbname: str | None = None,
        user: str | None = None,
        password: str | None = None,
        sslmode: str | None = None,
        ttl_days: int = 30,
    ) -> None:
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port if port is not None else int(os.getenv("POSTGRES_PORT", "5432"))
        self.dbname = dbname or os.getenv("POSTGRES_DB", "rossum_agent")
        self.user = user or os.getenv("POSTGRES_USER", "rossum")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "rossum")
        self.sslmode = sslmode or os.getenv("POSTGRES_SSLMODE")
        self.ttl = dt.timedelta(days=ttl_days)
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            url = sa.URL.create(
                "postgresql+psycopg",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.dbname,
            )
            connect_args: dict[str, Any] = {"connect_timeout": 5}
            if self.sslmode:
                connect_args["sslmode"] = self.sslmode
            self._engine = sa.create_engine(url, pool_recycle=1200, connect_args=connect_args)
        return self._engine

    def initialize(self) -> None:
        """Run Alembic migrations to bring the database schema up to date. Call once at startup."""
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
        alembic_cfg.attributes["engine"] = self.engine

        command.upgrade(alembic_cfg, "head")

    def _user_id_db(self, user_id: str | None) -> str:
        return user_id or ""

    def _expires_at(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC) + self.ttl

    def save_chat(
        self,
        user_id: str | None,
        chat_id: str,
        messages: list[dict[str, Any]],
        output_dir: str | Path | None = None,
        metadata: ChatMetadata | None = None,
    ) -> bool:
        try:
            uid = self._user_id_db(user_id)
            messages = [dict(msg) for msg in messages]
            meta_dict = (metadata or ChatMetadata()).to_dict()

            with self.engine.begin() as conn:
                # Preserve existing feedback
                row = conn.execute(
                    sa.select(chats_table.c.messages).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                    )
                ).first()
                if row:
                    for i, old_msg in enumerate(row.messages):
                        if i < len(messages) and old_msg.get("feedback") is not None:
                            messages[i]["feedback"] = old_msg["feedback"]

                values = {
                    "user_id": uid,
                    "chat_id": chat_id,
                    "messages": messages,
                    "output_dir": str(output_dir) if output_dir else None,
                    "metadata_": meta_dict,
                    "expires_at": self._expires_at(),
                }

                conn.execute(
                    insert(chats_table)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["user_id", "chat_id"],
                        set_={
                            "messages": values["messages"],
                            "output_dir": values["output_dir"],
                            "metadata_": values["metadata_"],
                            "expires_at": values["expires_at"],
                        },
                    )
                )

            files_saved = 0
            if output_dir:
                output_path = Path(output_dir) if isinstance(output_dir, str) else output_dir
                files_saved = self.save_all_files(chat_id, output_path)

            logger.info(
                f"Saved chat {chat_id} to PostgreSQL "
                f"(messages={len(messages)}, user: {user_id or 'shared'}, files={files_saved})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save chat {chat_id}: {e}", exc_info=True)
            return False

    def load_chat(self, user_id: str | None, chat_id: str, output_dir: Path | None = None) -> ChatData | None:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(
                        chats_table.c.messages,
                        chats_table.c.output_dir,
                        chats_table.c.metadata_,
                    ).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).first()

            if row is None:
                logger.info(f"Chat {chat_id} not found in PostgreSQL (user: {user_id or 'shared'})")
                return None

            messages = row.messages
            stored_output_dir = row.output_dir
            chat_metadata = ChatMetadata.from_dict(row.metadata_)

            files_loaded = 0
            if output_dir:
                files_loaded = self.load_all_files(chat_id, output_dir)

            logger.info(
                f"Loaded chat {chat_id} from PostgreSQL "
                f"({len(messages)} messages, {files_loaded} files, user: {user_id or 'shared'})"
            )
            return ChatData(messages=messages, output_dir=stored_output_dir, metadata=chat_metadata)
        except Exception as e:
            logger.error(f"Failed to load chat {chat_id}: {e}", exc_info=True)
            return None

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.begin() as conn:
                result = conn.execute(
                    sa.delete(chats_table).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                    )
                )
                deleted = result.rowcount > 0
            logger.info(f"Deleted chat {chat_id} from PostgreSQL (deleted={deleted}, user: {user_id or 'shared'})")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete chat {chat_id}: {e}", exc_info=True)
            return False

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(sa.literal(1)).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).first()
                return row is not None
        except Exception as e:
            logger.error(f"Failed to check if chat {chat_id} exists: {e}", exc_info=True)
            return False

    def is_connected(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            return True
        except Exception:
            return False

    def list_all_chats(self, user_id: str | None = None) -> list[dict[str, Any]]:
        try:
            uid = self._user_id_db(user_id)
            msg_count = sa.func.jsonb_array_length(chats_table.c.messages).label("message_count")
            first_msg = chats_table.c.messages[0].label("first_msg")

            with self.engine.connect() as conn:
                rows = conn.execute(
                    sa.select(
                        chats_table.c.chat_id,
                        msg_count,
                        first_msg,
                        chats_table.c.metadata_,
                    )
                    .where(
                        chats_table.c.user_id == uid,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                    .order_by(chats_table.c.created_at.desc())
                ).all()

            chats = [
                _build_chat_list_item(
                    row.chat_id,
                    row.message_count,
                    _preview_from_first_msg(row.first_msg),
                    ChatMetadata.from_dict(row.metadata_),
                )
                for row in rows
            ]

            logger.info(f"Found {len(chats)} chats in PostgreSQL (user: {user_id or 'shared'})")
            return chats
        except Exception as e:
            logger.error(f"Failed to list chats: {e}", exc_info=True)
            return []

    @staticmethod
    def _upsert_file(
        conn: sa.Connection, chat_id: str, filename: str, content: bytes, expires_at: dt.datetime
    ) -> None:
        """Insert or update a file row within an existing connection/transaction."""
        conn.execute(
            insert(chat_files_table)
            .values(chat_id=chat_id, filename=filename, size=len(content), content=content, expires_at=expires_at)
            .on_conflict_do_update(
                index_elements=["chat_id", "filename"],
                set_={"size": len(content), "content": content, "created_at": sa.func.now(), "expires_at": expires_at},
            )
        )

    def save_file(self, chat_id: str, file_path: Path | str, content: bytes | None = None) -> bool:
        try:
            if isinstance(file_path, str):
                file_path = Path(file_path)

            filename = file_path.name

            if content is None:
                try:
                    content = file_path.read_bytes()
                except FileNotFoundError:
                    logger.error(f"File not found: {file_path}")
                    return False

            with self.engine.begin() as conn:
                self._upsert_file(conn, chat_id, filename, content, self._expires_at())

            logger.info(f"Saved file {filename} for chat {chat_id} to PostgreSQL ({len(content)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to save file for chat {chat_id}: {e}", exc_info=True)
            return False

    def load_file(self, chat_id: str, filename: str) -> bytes | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(chat_files_table.c.content).where(
                        chat_files_table.c.chat_id == chat_id,
                        chat_files_table.c.filename == filename,
                        chat_files_table.c.expires_at > sa.func.now(),
                    )
                ).first()

            if row is None:
                logger.info(f"File {filename} not found for chat {chat_id}")
                return None

            content = bytes(row.content)
            logger.info(f"Loaded file {filename} for chat {chat_id} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"Failed to load file {filename} for chat {chat_id}: {e}", exc_info=True)
            return None

    def list_files(self, chat_id: str) -> list[dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    sa.select(
                        chat_files_table.c.filename,
                        chat_files_table.c.size,
                        chat_files_table.c.created_at,
                    ).where(
                        chat_files_table.c.chat_id == chat_id,
                        chat_files_table.c.expires_at > sa.func.now(),
                    )
                ).all()

            files = [
                {
                    "filename": row.filename,
                    "size": row.size,
                    "timestamp": row.created_at.isoformat(),
                }
                for row in rows
            ]
            logger.info(f"Found {len(files)} files for chat {chat_id}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files for chat {chat_id}: {e}", exc_info=True)
            return []

    def delete_file(self, chat_id: str, filename: str) -> bool:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sa.delete(chat_files_table).where(
                        chat_files_table.c.chat_id == chat_id,
                        chat_files_table.c.filename == filename,
                    )
                )
                deleted = result.rowcount > 0
            logger.info(f"Deleted file {filename} for chat {chat_id} (deleted={deleted})")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete file {filename} for chat {chat_id}: {e}", exc_info=True)
            return False

    def delete_all_files(self, chat_id: str) -> int:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(sa.delete(chat_files_table).where(chat_files_table.c.chat_id == chat_id))
                deleted = result.rowcount
            logger.info(f"Deleted {deleted} files for chat {chat_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete files for chat {chat_id}: {e}", exc_info=True)
            return 0

    def save_all_files(self, chat_id: str, output_dir: Path) -> int:
        try:
            if not output_dir.exists() or not output_dir.is_dir():
                logger.warning(f"Output directory does not exist: {output_dir}")
                return 0

            files = [f for f in output_dir.iterdir() if f.is_file()]
            if not files:
                return 0

            expires_at = self._expires_at()
            with self.engine.begin() as conn:
                for file_path in files:
                    self._upsert_file(conn, chat_id, file_path.name, file_path.read_bytes(), expires_at)

            logger.info(f"Saved {len(files)} files for chat {chat_id} to PostgreSQL")
            return len(files)
        except Exception as e:
            logger.error(f"Failed to save files for chat {chat_id}: {e}", exc_info=True)
            return 0

    def load_all_files(self, chat_id: str, output_dir: Path) -> int:
        loaded_count = 0
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            query = sa.select(
                chat_files_table.c.filename,
                chat_files_table.c.content,
            ).where(
                chat_files_table.c.chat_id == chat_id,
                chat_files_table.c.expires_at > sa.func.now(),
            )

            # Stream rows one at a time to avoid loading all file BYTEA contents into memory
            with self.engine.connect().execution_options(stream_results=True) as conn:
                for row in conn.execute(query).yield_per(1):
                    file_path = output_dir / row.filename
                    file_path.write_bytes(bytes(row.content))
                    loaded_count += 1

            logger.info(f"Loaded {loaded_count} files for chat {chat_id} from PostgreSQL")
            return loaded_count
        except Exception as e:
            logger.error(f"Failed to load files for chat {chat_id}: {e}", exc_info=True)
            return loaded_count

    def save_feedback(self, user_id: str | None, chat_id: str, turn_index: int, is_positive: bool) -> bool:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.begin() as conn:
                # Validate turn_index is within bounds
                msg_len = conn.execute(
                    sa.select(sa.func.jsonb_array_length(chats_table.c.messages)).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).scalar()

                if msg_len is None or turn_index >= msg_len:
                    return False

                # Update feedback in-place using jsonb_set
                conn.execute(
                    sa.update(chats_table)
                    .where(chats_table.c.user_id == uid, chats_table.c.chat_id == chat_id)
                    .values(
                        messages=sa.func.jsonb_set(
                            chats_table.c.messages,
                            pg_array([str(turn_index), "feedback"]),
                            sa.cast(sa.literal("true" if is_positive else "false"), JSONB),
                        )
                    )
                )

            logger.info(f"Saved feedback for chat {chat_id} turn {turn_index}: {is_positive}")
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback for chat {chat_id}: {e}", exc_info=True)
            return False

    def get_feedback(self, user_id: str | None, chat_id: str) -> dict[int, bool]:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(chats_table.c.messages).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).first()

                if row is None:
                    return {}

            result: dict[int, bool] = {}
            for i, msg in enumerate(row.messages):
                fb = msg.get("feedback")
                if fb is not None:
                    result[i] = fb
            return result
        except Exception as e:
            logger.error(f"Failed to get feedback for chat {chat_id}: {e}", exc_info=True)
            return {}

    def delete_feedback(self, user_id: str | None, chat_id: str, turn_index: int) -> bool:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.begin() as conn:
                # Check bounds and whether feedback exists at this index
                row = conn.execute(
                    sa.select(
                        sa.func.jsonb_array_length(chats_table.c.messages).label("msg_len"),
                        chats_table.c.messages[turn_index].op("?")("feedback").label("has_feedback"),
                    ).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).first()

                if row is None or turn_index >= row.msg_len or not row.has_feedback:
                    return False

                # Remove feedback key: replace element at turn_index with itself minus 'feedback'
                conn.execute(
                    sa.update(chats_table)
                    .where(chats_table.c.user_id == uid, chats_table.c.chat_id == chat_id)
                    .values(
                        messages=sa.func.jsonb_set(
                            chats_table.c.messages,
                            pg_array([str(turn_index)]),
                            sa.type_coerce(
                                chats_table.c.messages[turn_index].op("-")("feedback"),
                                JSONB,
                            ),
                        )
                    )
                )

            logger.info(f"Deleted feedback for chat {chat_id} turn {turn_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete feedback for chat {chat_id}: {e}", exc_info=True)
            return False

    def delete_all_feedback(self, user_id: str | None, chat_id: str) -> bool:
        try:
            uid = self._user_id_db(user_id)
            with self.engine.begin() as conn:
                row = conn.execute(
                    sa.select(chats_table.c.messages).where(
                        chats_table.c.user_id == uid,
                        chats_table.c.chat_id == chat_id,
                        chats_table.c.expires_at > sa.func.now(),
                    )
                ).first()

                if row is None:
                    return False

                messages: list[dict[str, Any]] = row.messages
                for msg in messages:
                    msg.pop("feedback", None)

                conn.execute(
                    sa.update(chats_table)
                    .where(chats_table.c.user_id == uid, chats_table.c.chat_id == chat_id)
                    .values(messages=messages)
                )

            logger.info(f"Deleted all feedback for chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete all feedback for chat {chat_id}: {e}", exc_info=True)
            return False

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            logger.info("Closed PostgreSQL connection pool")
