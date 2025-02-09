import websockets
import asyncio
import json
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import random
import logging

logging.basicConfig(level=logging.INFO)
logging.info("Starting mock backend...")

app = FastAPI(title="Cryostat Control API", description="Backend API for controlling the Lake Shore Model 335.")

# Store active WebSocket connections
active_connections = set()

# Fake WebSocket Server that sends mock data every second
# async def fake_backend():
#     # Specify the WebSocket server URI (localhost:8000 in this case)
#     async with websockets.serve(fake_websocket_endpoint, "localhost", 8000):
#         print("Fake backend running...")
#         await asyncio.Future()  # Run forever

# WebSocket endpoint that sends mock data to the connected client
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket endpoint that sends data to the frontend.
    """
    await websocket.accept()
    try:
        while True:
            # Simulate fake data: Random temperature and heater output
            fake_data = {
                "temperature": round(20 + 5 * (random.random() - 0.5), 2),  # Simulated temperature
                "heater_output": round(50 + 10 * (random.random() - 0.5), 2),  # Simulated heater output
            }
            # Send the mock data as JSON
            message = json.dumps(fake_data)
            await websocket.send_text(message)
            await asyncio.sleep(0.1)  # Simulate real-time updates
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)