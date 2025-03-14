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

async def perform_iv_measurement(source_meter: Keithley2400, 
                                    start_voltage: float, 
                                    stop_voltage: float, 
                                    step_voltage: float, 
                                    compliance_current: float, 
                                    source_voltage_range: float) -> dict:
    """
    Performs an I-V (current-voltage) measurement using a Keithley 2400 SourceMeter over a specified voltage range.

    This function configures the Keithley 2400 to source voltage and measure current. It then sweeps the voltage from
    `start_voltage` to `stop_voltage` in increments of `step_voltage`, measuring the current at each voltage point.
    It also attempts to retrieve and handle standard deviation measurements, if available from the instrument.

    Args:
        source_meter (Keithley2400): The Keithley 2400 instrument object, already initialized and connected.
        start_voltage (float): The starting voltage (in Volts) for the I-V sweep.
        stop_voltage (float): The ending voltage (in Volts) for the I-V sweep.
        step_voltage (float): The voltage increment (in Volts) between measurement points.
        compliance_current (float): The maximum allowed current (in Amperes) to protect the device under test.
        source_voltage_range (float): The voltage range (in Volts) to be used by the Keithley 2400. This must be 
                                      sufficient to cover the entire voltage sweep.

    Returns:
        dict: A dictionary containing the measurement results, with the following keys:
            - "voltages": A list of voltage values (floats) at which the measurements were taken.
            - "currents": A list of corresponding current values (floats) measured at each voltage.
            - "voltage_stds": A list of standard deviation values (floats or None) associated with each voltage measurement.
                              None is used if the standard deviation could not be retrieved or was invalid.

    Raises:
        Any exceptions raised by the Keithley 2400 instrument or the underlying communication adapter will be propagated.

    Example:
        async def main():
            adapter = SerialAdapter('/dev/ttyUSB0', baudrate=9600)
            keithley = Keithley2400(adapter)
            results = await perform_iv_measurement(keithley, -1, 1, 0.1, 0.01, 5)
            print(results)
            keithley.shutdown()

    """
    if source_meter is None:
        logging.error("SourceMeter not initialized in perform_iv_measurement()")
        return {}

    try:
        source_meter.reset()
        source_meter.use_front_terminals()
        source_meter.apply_voltage()
        source_meter.source_voltage_range = source_voltage_range
        source_meter.compliance_current = compliance_current
        source_meter.measure_current()
        source_meter.enable_source()

        voltages = np.arange(start_voltage, stop_voltage + step_voltage, step_voltage).tolist() # Convert to list for consistent output.
        currents = []
        voltage_stds = []

        for voltage in voltages:
            set_voltage(source_meter, voltage)
            await asyncio.sleep(0.1)  # Wait for the measurement to stabilize
            current = measure_current(source_meter)

            # Handle the standard deviation (if available)
            try:
                std_dev = source_meter.standard_devs[0]  # Assuming the standard deviation is stored in index 0
                # Check for invalid values (e.g., `9.91e+37`)
                if std_dev == 9.91e+37:
                    logging.warning(f"Invalid standard deviation for voltage {voltage}V, skipping standard deviation.")
                    std_dev = None
            except Exception as e:
                logging.error(f"Error reading standard deviation: {e}")
                std_dev = None

            currents.append(current)
            voltage_stds.append(std_dev)

        source_meter.disable_source()

        output = {
            "voltages": voltages,
            "currents": currents,
            "voltage_stds": voltage_stds
        }

        logging.warning(f"Returning output from IV measurement: {output}")
        return output

    except Exception as e:
        logging.error(f"An error occurred during IV measurement: {e}")
        return {}
    finally:
        try:
            source_meter.disable_source()
        except:
            pass

