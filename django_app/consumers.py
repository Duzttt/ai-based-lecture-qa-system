import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dashboard updates.

    Sends periodic updates about:
    - Indexing progress
    - Document count changes
    - Vector store statistics
    """

    async def connect(self):
        """Accept WebSocket connection and add to dashboard group."""
        self.room_group_name = "dashboard"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Send initial connection acknowledgment
        await self.send(
            text_data=json.dumps(
                {"type": "connected", "message": "Connected to dashboard updates"}
            )
        )

        # Start periodic updates
        asyncio.create_task(self.send_periodic_updates())

    async def disconnect(self, close_code):
        """Leave room group on disconnect."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def send_periodic_updates(self):
        """Send periodic status updates every 5 seconds."""
        try:
            while True:
                await asyncio.sleep(5)

                # Get current indexing state
                from django_app.views import _get_upload_indexing_state

                indexing_state = _get_upload_indexing_state()

                # Send update to this client
                await self.send(
                    text_data=json.dumps(
                        {"type": "indexing_status", "data": indexing_state}
                    )
                )
        except Exception:
            # Client disconnected, stop the task
            pass

    async def dashboard_update(self, event):
        """
        Handle dashboard update events from the channel layer.

        Expected event format:
        {
            "type": "dashboard.update",
            "data": {...}
        }
        """
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"type": "dashboard_update", "data": event["data"]})
        )

    async def indexing_progress(self, event):
        """
        Handle indexing progress events.

        Expected event format:
        {
            "type": "indexing.progress",
            "data": {
                "status": "running",
                "progress": 0.5,
                "current_file": "document.pdf",
                "chunks_processed": 100,
                "total_chunks": 200
            }
        }
        """
        await self.send(
            text_data=json.dumps({"type": "indexing_progress", "data": event["data"]})
        )


class UploadProgressConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time upload progress updates.
    """

    async def connect(self):
        """Accept WebSocket connection."""
        self.room_group_name = "upload_progress"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """Leave room group on disconnect."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def upload_progress(self, event):
        """
        Handle upload progress events.

        Expected event format:
        {
            "type": "upload.progress",
            "data": {
                "filename": "document.pdf",
                "status": "uploading",
                "progress": 0.5,
                "stage": "parsing" | "chunking" | "embedding" | "indexing"
            }
        }
        """
        await self.send(
            text_data=json.dumps({"type": "upload_progress", "data": event["data"]})
        )
