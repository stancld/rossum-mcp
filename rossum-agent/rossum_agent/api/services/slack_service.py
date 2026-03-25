from __future__ import annotations

import json
import logging

try:
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web.async_client import AsyncWebClient
except ImportError:
    AsyncWebClient = None  # ty:ignore[invalid-assignment]
    SlackApiError = None  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)


class SlackServiceError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class SlackService:
    def __init__(self, slack_bot_token: str) -> None:
        if AsyncWebClient is None:
            raise ImportError(
                "slack-sdk is required for Slack integration. Install it with: pip install rossum-agent[slack]"
            )

        self._client = AsyncWebClient(token=slack_bot_token)

    @staticmethod
    def _build_comment(
        reporter_name: str | None = None,
        user_id: str | None = None,
        organization_name: str | None = None,
        organization_id: int | None = None,
        queue_id: int | None = None,
        queue_name: str | None = None,
    ) -> str:
        header = "Conversation reported"
        if reporter_name:
            header += f" by *{reporter_name}*"
        if user_id:
            header += f" [{user_id}]"

        lines = [header, ""]
        if organization_name or organization_id:
            org_part = f"*Organization:* {organization_name}" if organization_name else "*Organization:*"
            if organization_id:
                org_part += f" [{organization_id}]"
            lines.append(org_part)
        if queue_name or queue_id:
            queue_part = f"*Queue:* {queue_name}" if queue_name else "*Queue:*"
            if queue_id:
                queue_part += f" [{queue_id}]"
            lines.append(queue_part)

        return "\n".join(lines).strip()

    async def post_conversation(
        self,
        channel: str,
        chat_id: str,
        messages: list[dict],
        reporter_name: str | None = None,
        user_id: str | None = None,
        organization_name: str | None = None,
        organization_id: int | None = None,
        queue_id: int | None = None,
        queue_name: str | None = None,
    ) -> str:
        comment = self._build_comment(reporter_name, user_id, organization_name, organization_id, queue_id, queue_name)
        conversation_json = json.dumps(
            {"chat_id": chat_id, "messages": messages},
            indent=2,
            ensure_ascii=False,
        )

        try:
            msg_response = await self._client.chat_postMessage(channel=channel, text=comment)
            channel_id = msg_response["channel"]
            thread_ts = msg_response["ts"]

            await self._client.files_upload_v2(
                channel=channel_id,
                content=conversation_json,
                filename=f"{chat_id}.json",
                title=f"Chat: {chat_id}",
                thread_ts=thread_ts,
            )
            return thread_ts
        except SlackApiError as e:
            logger.error("Slack API error: %s", e.response["error"])
            raise SlackServiceError(detail=f"Failed to post to Slack: {e.response['error']}") from e
