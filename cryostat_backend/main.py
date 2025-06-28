import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
import uvicorn
import json
from typing import List, Tuple, Dict
from temperature_scheduler import TemperatureScheduler
from status_and_setting_utils import *
import logging

logging.basicConfig(level=logging.WARNING)

app = FastAPI(title="Cryostat Control API", description="Backend API for controlling the Lake Shore Model 335.")

# Initialize connection
cryo = initialize_connection()
if cryo is None:
    raise RuntimeError("Failed to connect to the Cryostat Controller.")

# Store active WebSocket connections
active_connections = set()

temperature_scheduler_task = None

@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    try:
        status = fetch_status(cryo)
        return json.dumps(status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket endpoint that sends data to the frontend. """
    await websocket.accept()
    # Add the connection to the active connections set
    active_connections.add(websocket)
    try:
        while True:
            # Example: Sending structured JSON instead of empty data
            status = fetch_status(cryo)
            message = json.dumps(status)
            await websocket.send_text(message)
            await asyncio.sleep(0.25)  # Simulate real-time updates
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        raise e
        print(f"WebSocket error: {e}")
    finally:
        # Ensure the connection is removed from the active connections when it disconnects
        active_connections.discard(websocket)



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

@app.websocket("/start-temperature-schedule")
async def websocket_start_temperature_schedule(websocket: WebSocket):
    """WebSocket endpoint to start the temperature schedule."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            logging.warning(f"Received schedule data: {data}")

            setpoints = data.get("setpoints", [])
            threshold = data.get("threshold", 0.1)
            sustain_on_exit = data.get("sustain", False)
            hold_time = data.get("hold_time", 60)

            global temperature_scheduler_task
            if temperature_scheduler_task and temperature_scheduler_task.running:
                logging.warning("Stopping existing temperature scheduler before starting a new one.")
                temperature_scheduler_task.running = False

            def notify_callback(temp):
                asyncio.create_task(broadcast_temperature(temp))

            temperature_scheduler_task = TemperatureScheduler(cryo, heater_output=1, setpoints=setpoints, threshold=threshold, 
                                    hold_time=hold_time, sustain_on_exit=sustain_on_exit)
            logging.warning(f"Starting temperature scheduler with setpoints: {setpoints}, threshold: {threshold}, hold_time: {hold_time}, sustain_on_exit: {sustain_on_exit}")
            asyncio.create_task(temperature_scheduler_task.monitor_temperature(notify_callback))

            await websocket.send_text(json.dumps({"status": "Temperature schedule started"}))

    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))

async def broadcast_temperature(temp):
    """Notify all connected WebSocket clients about temperature stability."""
    message = json.dumps({"stable_temperature": temp})
    logging.warning(f"Broadcasting message: {message} to {len(active_connections)} connections")

    for connection in list(active_connections):  # Iterate over a copy to avoid modification issues
        try:
            logging.info(f"Sending to connection: {connection.client}")
            await connection.send_text(message)
        except Exception as e:
            logging.error(f"Failed to send message to connection {connection.client}: {e}")
            active_connections.discard(connection)  # Remove dead connections

    for connection in active_connections:
        try:
            await connection.send_text(message)
        except:
            pass  # Handle disconnections gracefully

@app.websocket("/stop-temperature-schedule")
async def websocket_stop_temperature_schedule(websocket: WebSocket):
    """WebSocket endpoint to stop the temperature schedule."""
    await websocket.accept()
    logging.warning("Stopping temperature schedule")
    global temperature_scheduler_task
    if temperature_scheduler_task:
        temperature_scheduler_task.running = False
        logging.warning("Temperature schedule stopped, starting to wait")
        await websocket.send_text(json.dumps({"status": "Temperature schedule stopped"}))
        logging.warning("Exiting")
    else:
        await websocket.send_text(json.dumps({"error": "No active temperature schedule"}))

@app.websocket("/heaters-off")
async def websocket_heaters_off(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        logging.info("Truning Heaters Off")
        cryo.all_heaters_off()
        await websocket.send_text("Heaters turned off")


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