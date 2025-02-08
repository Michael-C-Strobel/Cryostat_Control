import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from lakeshore import Model335
from cryostat_control import initialize_connection, set_pid_values, set_heater_settings, fetch_status

app = FastAPI(title="Cryostat Control API", description="Backend API for controlling the Lake Shore Model 335.")

# Initialize connection
cryo = initialize_connection()
if cryo is None:
    raise RuntimeError("Failed to connect to the Cryostat Controller.")

# Store active WebSocket connections
active_connections = set()


class PIDRequest(BaseModel):
    loop: int
    p_value: float
    i_value: float
    d_value: float


class HeaterSettingsRequest(BaseModel):
    heater_resistance: int  
    max_current: float
    display_setting: int  


@app.post("/set_pid")
async def set_pid(request: PIDRequest):
    """Set PID values."""
    try:
        set_pid_values(cryo, request.loop, request.p_value, request.i_value, request.d_value)
        return {"message": "PID values updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/set_heater")
async def set_heater(request: HeaterSettingsRequest):
    """Set heater settings."""
    try:
        set_heater_settings(cryo, request.heater_resistance, request.max_current, request.display_setting)
        return {"message": "Heater settings updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    try:
        return fetch_status(cryo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time cryostat updates."""
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            status = fetch_status(cryo)  # Fetch current status
            await websocket.send_json(status)
            await asyncio.sleep(2)  # Update every 2 seconds
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shut down the connection."""
    global cryo
    if cryo:
        cryo.all_heaters_off()
        print("Cryostat heaters turned off before shutdown.")
