import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocketState
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

async def handle_initialize(websocket: WebSocket, data: dict):
    """Handle SourceMeter initialization."""
    global source_meter
    adapter = str(data.get("adapter", None))
    logging.info(f"Initializing with adapter: {adapter}")

    if source_meter is None and adapter:
        source_meter = await initialize_connection(adapter)  # Async initialization

    if source_meter:
        await websocket.send_json({"status": "Connection initialized"})
    else:
        await websocket.send_json({"status": "Failed to connect"})

async def handle_measure_iv_curve(websocket: WebSocket, data: dict):
    """Handle IV curve measurement request."""
    if source_meter is None:
        await websocket.send_json({"error": "SourceMeter not initialized"})
        return

    try:
        key = data["key"]
        type = data["type"]
        if type == "voltage_sweep":
            logging.info(f"Measuring IV curve with key: {key}")
            start_voltage = data["start_voltage"]
            stop_voltage = data["stop_voltage"]
            step_voltage = data["step_voltage"]
            compliance_current = data.get("compliance_current", 0.1)
            source_voltage_range = data.get("source_voltage_range", 5.0)

            logging.info(f"Measuring IV: start={start_voltage}, stop={stop_voltage}, step={step_voltage}")
            iv_curve = await perform_iv_measurement_voltage_sweep(
                source_meter, start_voltage, stop_voltage, step_voltage, compliance_current, source_voltage_range
            )
        elif type == "current_sweep":
            logging.info(f"Measuring IV curve with key: {key}")
            start_current = data["start_current"]
            stop_current = data["stop_current"]
            step_current = data["step_current"]
            compliance_voltage = data.get("compliance_voltage", 5.0)
            source_current_range = data.get("source_current_range", 0.1)

            logging.info(f"Measuring IV: start={start_current}, stop={stop_current}, step={step_current}")
            iv_curve = await perform_iv_measurement_current_sweep(
                source_meter, start_current, stop_current, step_current, compliance_voltage, source_current_range
            )
        else:
            logging.error(f"Invalid measurement type: {type}")
            await websocket.send_json({"error": "Invalid measurement type"})
            return

        await websocket.send_json({"iv_curve": iv_curve, "key": str(key)})
    except Exception as e:
        logging.error(f"Error during IV measurement: {str(e)}")
        await websocket.send_json({"error": str(e)})

async def handle_status(websocket: WebSocket):
    """Send SourceMeter status."""
    if source_meter:
        status = fetch_status(source_meter)  # Fetch current device status
        await websocket.send_json({"status": status})
    else:
        await websocket.send_json({"status": "No device connected"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for single-request connections (e.g., from Celery)."""
    await websocket.accept()

    try:
        data = await websocket.receive_json()
        command = data.get("command")

        command_handlers = {
            "initialize": handle_initialize,
            "measure_iv_curve": handle_measure_iv_curve,
            "status": handle_status,
        }

        handler = command_handlers.get(command)
        if handler:
            await handler(websocket, data)
        else:
            await websocket.send_json({"error": "Unknown command"})

    except WebSocketDisconnect:
        logging.info("Client disconnected")
    except Exception as e:
        logging.exception(f"WebSocket error: {e}")
    finally:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()


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
