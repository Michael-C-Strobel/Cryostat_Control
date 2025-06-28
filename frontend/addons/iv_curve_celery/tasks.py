from addons.iv_curve_celery.celery_app import celery_app
import asyncio
import logging

import websockets
import json
import os

from celery.signals import task_success
from redis import Redis

# Get redis client from celery app context
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
if not CELERY_BROKER_URL:
    raise ValueError("CELERY_BROKER_URL must be set in environment variables.")
redis_client = Redis.from_url(CELERY_BROKER_URL)


# Asynchronous WebSocket function for connection
async def send_websocket_request(command, payload={}):
    """Helper function to send and receive messages via WebSocket."""
    url = "ws://keithley-2400-backend:8001/ws"
    try:
        async with websockets.connect(url) as websocket:
            request = {"command": command, **payload}
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            return json.loads(response)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        return {"status": "Error", "detail": str(e)}
    

@celery_app.task(
    bind=True,
    name="addons.iv_curve_celery.tasks.run_sourcemeter_measurement"
)
def run_sourcemeter_measurement(self, command, payload):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_websocket_request(command, payload))
        return result
    except Exception as e:
        logging.error(f"Celery task error: {e}")
        return {"status": "Error", "detail": str(e)}

# This is a part of a workaround to avoid storing the task_id, since the dcc.Store approach is bugged
@task_success.connect
def task_succeeded_handler(sender=None, result=None, **kwargs):
    logging.warning("[Signal] task_success triggered")
    try:
        payload = {
            "task_id": sender.request.id,
            "result": result,
        }
        redis_client.rpush("sourcemeter:results", json.dumps(payload))
        print(f"[Signal] Stored result for task {payload['task_id']}")
    except Exception as e:
        print(f"[Signal] Failed to store result: {e}")