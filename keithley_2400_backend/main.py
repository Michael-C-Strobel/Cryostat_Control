import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
import uvicorn
import json
from typing import List, Tuple, Dict
from utils import *
import logging

logging.basicConfig(level=logging.WARNING)

app = FastAPI(title="Keithley 2400 API", description="Backend API for controlling the Keithley 2400.")

# Initialize connection
source_meter = None

# Store active WebSocket connections
active_connections = set()

@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    raise NotImplementedError("/status is not implemented")

@app.get("/connection_options")
async def get_connection_options():
    return query_connections()

# Endpoint to initialize connection
@app.post("/initialize")
async def initialize_connection(websocket: WebSocket):
    """Initialize the connection to the Keithley 2400 SourceMeter."""
    await websocket.accept()
    global source_meter
    data = await websocket.receive_json()
    adapter = str(data.get("adapter", ""))
    try:
        if source_meter is not None:
            source_meter = initialize_connection(adapter)
        if source_meter is None:
            logging.error("Failed to connect to the Keithley 2400.")
            return {"status": "Failed to connect."}
        return {"status": "Connection initialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/measure_iv_curve")
async def measure_iv_curve(voltages: List[float]):
    """Measure the current for a list of provided voltages and return the I-V curve."""
    if source_meter is None:
        raise HTTPException(status_code=400, detail="SourceMeter not initialized.")
    
    try:
        iv_curve = await perform_iv_measurement(source_meter, voltages)
        return {"iv_curve": iv_curve}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket endpoint that sends data to the frontend.
    """
    await websocket.accept()
    try:
        while True:
            message = json.dumps(fetch_status(source_meter))    # Send current status
            await websocket.send_text(message)
            await asyncio.sleep(0.1)  # Simulate real-time updates
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        raise e
        print(f"WebSocket error: {e}")

@app.get("/health")
def health():
    """Health check endpoint. Docker will stop if this fails to respond 
    (see docker-compose.yml)
    """
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)