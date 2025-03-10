import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
import uvicorn
import json
from typing import List, Dict
from utils import *
import logging

logging.basicConfig(level=logging.WARNING)

app = FastAPI(title="Keithley 2400 API", description="Backend API for controlling the Keithley 2400.")

# Initialize connection
source_meter = None

# Store active WebSocket connections
active_connections = set()

###### Websocket Endpoints ######

@app.websocket("/initialize")
async def initialize_ws_connection(websocket: WebSocket):
    """Initialize the connection to the Keithley 2400 SourceMeter."""
    await websocket.accept()
    global source_meter

    try:
        data = await websocket.receive_json()
        adapter = str(data.get("adapter", None))
        logging.warning(f"got data {data}")
        logging.warning(f"got adapter {adapter}")

        if source_meter is None and adapter is not None:
            logging.warning("Initializing Connection...")
            source_meter = await initialize_connection(adapter)  # Adjusted for async initialization

        if source_meter is None:
            logging.error("Failed to connect to the Keithley 2400.")
            await websocket.send_json({"status": "Failed to connect."})
            await websocket.close()
            return

        await websocket.send_json({"status": "Connection initialized"})
        active_connections.add(websocket)  # Track connection for real-time updates

    except Exception as e:
        logging.error(f"Error initializing connection: {str(e)}")
        await websocket.send_json({"status": "Error", "detail": str(e)})
        await websocket.close()


@app.websocket("/measure_iv_curve")
async def measure_iv_curve(websocket: WebSocket, voltages: List[float]):
    """Measure the current for a list of provided voltages and return the I-V curve."""
    if source_meter is None:
        raise HTTPException(status_code=400, detail="SourceMeter not initialized.")
    
    try:
        logging.warning(f"Performing IV measurement in backend main.py {voltages}")
        iv_curve = await perform_iv_measurement(source_meter, voltages)
        await websocket.send_json({"iv_curve": iv_curve})
    except Exception as e:
        logging.error(f"Error during IV measurement: {str(e)}")
        await websocket.send_json({"error": str(e)})


@app.websocket("/ws")
async def websocket_status(websocket: WebSocket):
    """WebSocket endpoint that sends data to the frontend."""
    await websocket.accept()
    try:
        while True:
            if source_meter:
                message = json.dumps(fetch_status(source_meter))  # Send current status
                await websocket.send_text(message)
                await asyncio.sleep(0.1)  # Simulate real-time updates
            else:
                await asyncio.sleep(1)  # If no source meter, wait before trying again
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logging.info("Client disconnected.")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")


###### HTTP Endpoints ######

@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    if source_meter is None:
        raise HTTPException(status_code=400, detail="SourceMeter not initialized.")
    return fetch_status(source_meter)


@app.get("/connection_options")
async def get_connection_options():
    """Fetch connection options over HTTP."""
    try:
        options = query_connections()  # Logic to get the connection options
        return {"options": options}
    except Exception as e:
        logging.error(f"Error while querying connection options: {str(e)}")
        return {"error": str(e)}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
