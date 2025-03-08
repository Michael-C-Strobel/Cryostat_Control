from pymeasure.instruments.keithley import Keithley2400
import serial.tools.list_ports
from typing import List, Dict, Tuple
import asyncio
import logging

"""
Input range of volatage + Number of points
Measure current

Plot it them all together on a graph

Add option to download data
"""

def query_connections() -> List:
    """Return set of options for USB connections"""
    ports = list(serial.tools.list_ports.comports())

    usb_ports = [
        (port.device, port.description)  # Use port.device for value, port.description for label
        for port in ports
        if 'usb' in str(port.description).lower()  # Filter based on PL2303 chipset
    ]
    dropdown_options = [{'label': description, 'value': device} for device, description in usb_ports]
    return dropdown_options


def initialize_connection(adapter: str = "GPIB::1") -> Keithley2400:
    """Initializes the connection to the Keithley 2400 SourceMeter."""
    try:
        source_meter = Keithley2400(adapter)
        return source_meter
    except Exception as e:
        logging.error(f"Error initializing connection: {e}")
        return None

def fetch_status(source_meter: Keithley2400) -> Dict:
    """Fetches the status of the Keithley 2400 SourceMeter."""
    if source_meter is None:
        return {}

    try:
        status = {
            "voltage": source_meter.voltage,
            "current": source_meter.current,
            "source_mode": source_meter.source_mode,
            "measure_mode": source_meter.measure_mode,
        }
        return status
    except Exception as e:
        logging.error(f"Error fetching status: {e}")
        return {}

def set_voltage(source_meter: Keithley2400, voltage: float):
    """Sets the voltage of the Keithley 2400 SourceMeter."""
    if source_meter is None:
        logging.error("SourceMeter not initialized in set_voltage()")
        return

    try:
        source_meter.voltage = voltage
    except Exception as e:
        prlogging.errorint(f"Error setting voltage: {e}")

def measure_current(source_meter: Keithley2400) -> float:
    """Measures the current from the Keithley 2400 SourceMeter."""
    if source_meter is None:
        logging.error("SourceMeter not initialized in measure_current()")
        return

    try:
        return source_meter.current
    except Exception as e:
        logging.error(f"Error measuring current: {e}")
        return 0.0

async def perform_iv_measurement(source_meter, voltages: List[float]) -> List[Tuple[float, float]]:
    """Perform the I-V measurement for the provided list of voltages."""
    if source_meter is None:
        logging.error("SourceMeter not initialized in perform_iv_measurement()")
        return []
    
    voltages = []
    currents = []
    for voltage in voltages:
        set_voltage(source_meter, voltage)
        await asyncio.sleep(0.1)  # Wait for the measurement to stabilize
        current = measure_current(source_meter)
        voltages.append(voltage)
        currents.append(current)
    return {
        "voltages": voltages,
        "currents": currents
    }