import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import uvicorn
import json
from status_and_setting_utils import *
from setter_utils import *
import logging

logging.basicConfig(level=logging.WARNING)

app = FastAPI(title="Cryostat Control API", description="Backend API for controlling the Lake Shore Model 335.")

# Initialize connection
cryo = initialize_connection()
if cryo is None:
    raise RuntimeError("Failed to connect to the Cryostat Controller.")

# Store active WebSocket connections
active_connections = set()

@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    try:
        return json.dumps(fetch_status(cryo))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket endpoint that sends data to the frontend.
    """
    await websocket.accept()
    try:
        while True:
            # Example: Sending structured JSON instead of empty data
            message = json.dumps(fetch_status(cryo))
            await websocket.send_text(message)
            await asyncio.sleep(0.1)  # Simulate real-time updates
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        raise e
        print(f"WebSocket error: {e}")


@app.websocket("/set-heater-state")
async def websocket_set_heater(websocket: WebSocket):
    """ WebSocket endpoint that sets the heater state.

    # Incoming Data
    #  {'pid_gain': None, 
    # 'pid_integral': None, 
    # 'pid_ramp_rate': None, 
    # 'heater_state': 'on', 
    # 'heater_resistance': None, 
    # 'max_current': None, 
    # 'display_settings': None}

    # TODO: Use set_pid_values() from status_and_setting_utils.py
    # TODO: Use set_heater_settings() from status_and_setting_utils.py
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            logging.warning(f"Received data: {data}")
            
            if 'pid_gain' in data and 'pid_integral' in data and 'pid_ramp_rate' in data:
                set_pid_values(cryo, 1, data['pid_gain'], data['pid_integral'], data['pid_ramp_rate'])
            else:
                logging.warning("Recieved invalid message for set_pid_values")

            if 'heater_resistance' in data and 'max_current' in data and 'heater_range' in data:
                set_heater_settings(cryo, 1, data['heater_resistance'], data['max_current'], data['heater_range'])
            else:
                logging.warning("Recieved invalid message for set_heater_settings")

            await websocket.send_text(json.dumps({"status": "settings updated"}))
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))

@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shut down the connection."""
    global cryo
    if cryo:
        cryo.all_heaters_off()
        print("Cryostat heaters turned off before shutdown.")

@app.get("/health")
def health():
    """Health check endpoint. Docker will stop if this fails to respond 
    (see docker-compose.yml)
    """
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)