import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


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
        self._periodic_task = None

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "Connected to dashboard updates"
        }))

        self._periodic_task = asyncio.create_task(self.send_periodic_updates())

    async def disconnect(self, close_code):
        """Leave room group on disconnect."""
        if self._periodic_task is not None:
            self._periodic_task.cancel()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def send_periodic_updates(self):
        """Send periodic status updates every 5 seconds."""
        try:
            while True:
                await asyncio.sleep(5)

                from django_app.views import _get_upload_indexing_state
                indexing_state = _get_upload_indexing_state()

                await self.send(text_data=json.dumps({
                    "type": "indexing_status",
                    "data": indexing_state
                }))
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in periodic dashboard update")
    
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
        await self.send(text_data=json.dumps({
            "type": "dashboard_update",
            "data": event["data"]
        }))
    
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
        await self.send(text_data=json.dumps({
            "type": "indexing_progress",
            "data": event["data"]
        }))


class UploadProgressConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time upload progress updates.
    """
    
    async def connect(self):
        """Accept WebSocket connection."""
        self.room_group_name = "upload_progress"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Leave room group on disconnect."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
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
        await self.send(text_data=json.dumps({
            "type": "upload_progress",
            "data": event["data"]
        }))
