from pymeasure.instruments.keithley import Keithley2400
from pymeasure.adapters import SerialAdapter
import serial.tools.list_ports
from typing import List, Dict, Tuple
import asyncio
import logging


logging.basicConfig(level=logging.WARNING)


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


async def initialize_connection(adapter: str):
    """Handles the asynchronous initialization of the SourceMeter connection."""
    # Add the logic to connect to your SourceMeter based on the adapter
    # Return a mock object or real connection
    logging.warning(f"Initializing connection for adapter: {adapter}")
    adapter = SerialAdapter(adapter, baudrate=9600, timeout=2, parity='N', stopbits=1, rtscts=False)
    adapter.write_termination = "\n"
    logging.warning(f"Adapter created: {adapter}")
    source_meter = Keithley2400(adapter)    # adapter = '/dev/ttyUSB1'
    logging.warning("Keithley2400 created")
    source_meter.reset()
    logging.warning("Keithley2400 reset")
    source_meter.use_front_terminals()
    logging.warning("Keithley2400 terminals set")
    return source_meter

def fetch_status(source_meter: Keithley2400) -> Dict:
    """Fetches the status of the Keithley 2400 SourceMeter."""
    if source_meter is None:
        return {}

    try:
        status = {
            "device": source_meter.ask("*IDN?"),
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

async def perform_iv_measurement(source_meter, voltages: List[float]) -> dict:
    """Perform the I-V measurement for the provided list of voltages, handling standard deviations."""
    if source_meter is None:
        logging.error("SourceMeter not initialized in perform_iv_measurement()")
        return {}

    # Prepare lists to store the measurement results
    currents = []
    voltage_stds = []

    for voltage in voltages:
        set_voltage(source_meter, voltage)
        await asyncio.sleep(0.1)  # Wait for the measurement to stabilize
        
        # Get the current measurement and the standard deviation (if available)
        current = measure_current(source_meter)
        
        # Handle the standard deviation (assuming it's provided directly by the sourcemeter)
        try:
            std_dev = source_meter.standard_devs[0]  # Assuming the standard deviation is stored in index 0
            # Check for invalid values (e.g., `9.91e+37`)
            if std_dev == 9.91e+37:
                logging.warning(f"Invalid standard deviation for voltage {voltage}V, skipping measurement.")
                std_dev = None  # You can set to None or handle as needed
        except Exception as e:
            logging.error(f"Error reading standard deviation: {e}")
            std_dev = None  # Fallback to None if there's an issue

        # Append the measurements and standard deviation
        currents.append(current)
        voltage_stds.append(std_dev)

    # Return the results as a dictionary
    return {
        "voltages": voltages,
        "currents": currents,
        "voltage_stds": voltage_stds
    }
