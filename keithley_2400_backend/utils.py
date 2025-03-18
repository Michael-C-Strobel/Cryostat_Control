from pymeasure.instruments.keithley import Keithley2400
from pymeasure.adapters import SerialAdapter
import serial.tools.list_ports
from typing import List, Dict, Tuple
import asyncio
import logging

import asyncio

import numpy as np
import time


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

def set_voltage(sourcemeter: Keithley2400, voltage: float) -> None:
    """Sets the source voltage on the Keithley 2400."""
    sourcemeter.source_voltage = voltage

def measure_current(sourcemeter: Keithley2400) -> float:
    """Measures the current using the Keithley 2400."""
    return sourcemeter.current

async def perform_iv_measurement(source_meter: 'Keithley2400', 
                                start_voltage: float, 
                                stop_voltage: float, 
                                step_voltage: float, 
                                compliance_current: float, 
                                source_voltage_range: float,
                                num_averages: int = 10,
                                nplc: float = 1) -> dict:
    """
    Performs an I-V (current-voltage) measurement using a Keithley 2400 SourceMeter over a specified voltage range,
    utilizing the instrument's built-in averaging and NPLC settings.

    Args:
        source_meter (Keithley2400): The Keithley 2400 instrument object, already initialized and connected.
        start_voltage (float): The starting voltage (in Volts) for the I-V sweep.
        stop_voltage (float): The ending voltage (in Volts) for the I-V sweep.
        step_voltage (float): The voltage increment (in Volts) between measurement points.
        compliance_current (float): The maximum allowed current (in Amperes) to protect the device under test.
        source_voltage_range (float): The voltage range (in Volts) to be used by the Keithley 2400.
        num_averages (int): The number of measurements to average at each voltage point.
        nplc (float): Number of power line cycles (NPLC) for noise reduction.
    Returns:
        dict: A dictionary containing the measurement results, with the following keys:
            - "voltages": A list of voltage values (floats) at which the measurements were taken.
            - "average_currents": A list of corresponding average current values (floats) measured at each voltage.
    """
    if source_meter is None:
        logging.error("SourceMeter not initialized in perform_iv_measurement()")
        return {}

    try:
        source_meter.reset()
        source_meter.use_front_terminals()
        source_meter.apply_voltage(voltage_range=source_voltage_range, compliance_current=compliance_current)
        source_meter.measure_current(nplc=nplc)
        source_meter.filter_count = num_averages
        source_meter.filter_state = "ON"
        source_meter.filter_type = "REP" # Repeat filter
        source_meter.enable_source()
        source_meter.auto_output_off = False #keep output on during sweep

        voltages = np.arange(start_voltage, stop_voltage + step_voltage, step_voltage).tolist()
        average_currents = []

        for voltage in voltages:
            source_meter.source_voltage = voltage
            await asyncio.sleep(0.1)  # Allow time to settle
            average_currents.append(source_meter.current)

        source_meter.disable_source()
        source_meter.filter_state = "OFF" #turn off filter.

        output = {
            "voltages": voltages,
            "currents": average_currents,
        }

        logging.warning(f"Returning output from IV measurement: {output}")
        return output

    except Exception as e:
        logging.error(f"An error occurred during IV measurement: {e}")
        return {}
    finally:
        try:
            source_meter.disable_source()
            source_meter.filter_state = "OFF"
        except:
            pass

