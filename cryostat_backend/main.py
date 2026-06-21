import asyncio
from fastapi import FastAPI, HTTPException, Request
import uvicorn
import json
from typing import List, Tuple, Dict, Optional
from temperature_scheduler import TemperatureScheduler
from status_and_setting_utils import *
import logging
from celery_app import celery_app
from celery.result import AsyncResult
import numpy as np

logging.basicConfig(level=logging.WARNING)
# Suppress uvicorn access logs (every /status poll) while keeping error logs.
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="Cryostat Control API", description="Backend API for controlling the Lake Shore Model 335.")

# Initialize connection
cryo = initialize_connection()
if cryo is None:
    raise RuntimeError("Failed to connect to the Cryostat Controller.")

temperature_scheduler_task = None


def build_iv_curve_payload(stable_temp: float, iv_curve_params: Dict) -> Optional[Dict]:
    """Build the payload for the sourcemeter measurement Celery task."""
    if not iv_curve_params:
        return None

    sweep_type = iv_curve_params.get("sweep_type")
    if sweep_type == "voltage_sweep":
        v_lb = float(iv_curve_params["voltage_lower"])
        v_ub = float(iv_curve_params["voltage_upper"])
        v_step = float(iv_curve_params["voltage_step"])
        if v_step == 0.0:
            logging.error("Voltage Step was Zero")
            return None
        voltages = list(np.arange(v_lb, v_ub, v_step))
        return {
            "key": str(stable_temp),
            "type": "voltage_sweep",
            "start_voltage": voltages[0],
            "stop_voltage": voltages[-1],
            "step_voltage": v_step,
            "compliance_current": iv_curve_params["compliance_current"],
            "source_voltage_range": iv_curve_params["voltage_range"],
        }
    elif sweep_type == "current_sweep":
        c_lb = float(iv_curve_params["current_lower"])
        c_ub = float(iv_curve_params["current_upper"])
        c_step = float(iv_curve_params["current_step"])
        if c_step == 0.0:
            logging.error("Current Step was Zero")
            return None
        currents = list(np.arange(c_lb, c_ub, c_step))
        return {
            "key": str(stable_temp),
            "type": "current_sweep",
            "start_current": currents[0],
            "stop_current": currents[-1],
            "step_current": c_step,
            "compliance_voltage": iv_curve_params["compliance_voltage"],
            "source_current_range": iv_curve_params["current_range"],
        }
    else:
        logging.error(f"Unknown sweep type: {sweep_type}")
        return None


async def run_iv_curve_measurement(stable_temp: float, iv_curve_params: Dict):
    """Enqueue the sourcemeter measurement and wait for it to complete."""
    payload = build_iv_curve_payload(stable_temp, iv_curve_params)
    if payload is None:
        logging.warning("No IV curve payload generated; skipping measurement")
        return

    logging.warning(f"[Scheduler] Queuing IV curve measurement at {stable_temp} K with payload: {payload}")
    task = celery_app.send_task("addons.iv_curve_celery.tasks.run_sourcemeter_measurement", args=["measure_iv_curve", payload])
    result_obj = AsyncResult(task.id, app=celery_app)

    # Poll the Celery result asynchronously without blocking the event loop.
    while not result_obj.ready():
        await asyncio.sleep(0.5)

    if result_obj.successful():
        logging.warning(f"[Scheduler] IV curve measurement complete: {result_obj.result}")
    else:
        logging.error(f"[Scheduler] IV curve measurement failed: {result_obj.result}")

@app.get("/status")
async def get_status():
    """Fetch temperature and heater output."""
    try:
        status = fetch_status(cryo)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/set-heater-state")
async def set_heater_state(request: Request):
    """REST endpoint to set the heater state.

    Incoming JSON:
    {
        "pid_gain": ...,
        "pid_integral": ...,
        "pid_ramp_rate": ...,
        "heater_resistance": ...,
        "max_current": ...,
        "heater_range": ...
    }
    """
    try:
        data = await request.json()
        logging.info(f"Received heater state: {data}")

        if 'pid_gain' in data and 'pid_integral' in data and 'pid_ramp_rate' in data:
            set_pid_values(cryo, 1, data['pid_gain'], data['pid_integral'], data['pid_ramp_rate'])
        else:
            logging.warning("Received invalid message for set_pid_values")

        if 'heater_resistance' in data and 'max_current' in data and 'heater_range' in data:
            set_heater_settings(cryo, 1, data['heater_resistance'], data['max_current'], data['heater_range'])
        else:
            logging.warning("Received invalid message for set_heater_settings")

        return {"status": "settings updated"}
    except Exception as e:
        logging.error(f"Error setting heater state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/start-temperature-schedule")
async def start_temperature_schedule(request: Request):
    """REST endpoint to start the temperature schedule."""
    try:
        data = await request.json()
        logging.info(f"Received schedule data: {data}")

        setpoints = data.get("setpoints", [])
        threshold = data.get("threshold", 0.1)
        sustain_on_exit = data.get("sustain", False)
        iv_curve_params = data.get("iv_curve_params")

        global temperature_scheduler_task
        if temperature_scheduler_task and temperature_scheduler_task.running:
            logging.warning("Stopping existing temperature scheduler before starting a new one.")
            temperature_scheduler_task.running = False

        async def on_stable(temp):
            if iv_curve_params:
                await run_iv_curve_measurement(temp, iv_curve_params)

        temperature_scheduler_task = TemperatureScheduler(
            cryo, heater_output=1, setpoints=setpoints, threshold=threshold,
            sustain_on_exit=sustain_on_exit, iv_curve_params=iv_curve_params
        )
        logging.info(f"Starting temperature scheduler with setpoints: {setpoints}, threshold: {threshold}, sustain_on_exit: {sustain_on_exit}, iv_curve_params: {iv_curve_params is not None}")
        asyncio.create_task(temperature_scheduler_task.monitor_temperature(on_stable))

        return {"status": "Temperature schedule started"}
    except Exception as e:
        logging.error(f"Error starting temperature schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop-temperature-schedule")
async def stop_temperature_schedule():
    """REST endpoint to stop the temperature schedule."""
    logging.info("Stopping temperature schedule")
    global temperature_scheduler_task
    if temperature_scheduler_task:
        temperature_scheduler_task.running = False
        logging.info("Temperature schedule stopped")
        return {"status": "Temperature schedule stopped"}
    else:
        return {"error": "No active temperature schedule"}


@app.post("/heaters-off")
async def heaters_off():
    """REST endpoint to turn off all heaters."""
    logging.info("Turning heaters off")
    cryo.all_heaters_off()
    return {"status": "Heaters turned off"}


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