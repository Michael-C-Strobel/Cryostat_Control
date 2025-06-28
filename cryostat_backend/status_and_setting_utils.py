from lakeshore import Model335
import logging

def initialize_connection(port=57600):
    """
    Initializes the connection to the Lake Shore Model 335.
    
    Args:
        port (int): The communication port. Default is 57600.
    
    Returns:
        Model335 instance.
    """
    try:
        cryo = Model335(port, timeout=60.0)
        return cryo
    except Exception as e:
        logging.error(f"Error initializing connection: {e}")
        return None


def set_pid_values(cryo, loop, p_value, i_value, d_value):
    """
    Sets the PID values for temperature control.

    Args:
        cryo (Model335): The initialized cryostat controller object.
        loop (int): The control loop (1 or 2).
        p_value (float): Proportional gain.
        i_value (float): Integral gain.
        d_value (float): Derivative gain.
    """
    try:
        cryo.set_heater_pid(loop, p_value, i_value, d_value)
        logging.warning(f"PID values set: P={p_value}, I={i_value}, D={d_value}")
    except Exception as e:
        logging.error(f"Error setting PID values: {e}")

def set_heater_settings(cryo, heater_num, heater_resistance, max_current, heater_range):
    """
    Configures the heater settings.

    Args:
        cryo (Model335): The initialized cryostat controller object.
        heater_resistance: Heater resistance setting (e.g., cryo.HeaterResistance.HEATER_25_OHM).
        max_current (float): Maximum heater current.
        display_setting: Heater output display mode (e.g., cryo.HeaterOutputDisplay.POWER).
        heater_range: Heater Range (str)
    """
    try:
        display_setting  = cryo.HeaterOutputDisplay.POWER
        if heater_num == 1:
            cryo.set_heater_setup_one(heater_resistance, max_current, display_setting)
            logging.warning(  f"Heater one settings applied: \
                            Resistance={heater_resistance}, \
                            Max Current={max_current}, \
                            Display={display_setting}, \
                            Heater Range={heater_range}")
        elif heater_num == 2:
            cryo.set_heater_setup_two(heater_resistance, max_current, display_setting)
            logging.warning(  f"Heater two settings applied: \
                            Resistance={heater_resistance}, \
                            Max Current={max_current}, \
                            Display={display_setting}, \
                            Heater Range={heater_range}")

        # Set heater range
        heater_range = str(heater_range).upper()
        if heater_range == "OFF":
            cryo.set_heater_range(heater_num, cryo.HeaterRange.OFF)
            logging.warning(f"Setting heater number {heater_num} to OFF")
        elif heater_range == "LOW":
            cryo.set_heater_range(heater_num, cryo.HeaterRange.LOW)
            logging.warning(f"Setting heater number {heater_num} to LOW")
        elif heater_range == "MEDIUM":
            cryo.set_heater_range(heater_num, cryo.HeaterRange.MEDIUM)
            logging.warning(f"Setting heater number {heater_num} to MEDIUM")
        elif heater_range == "HIGH":
            cryo.set_heater_range(heater_num, cryo.HeaterRange.HIGH)
            logging.warning(f"Setting heater number {heater_num} to HIGH")


    except Exception as e:
        print(f"Error setting heater settings: {e}")


def fetch_status(cryo):
    """
    Fetches the current status, including temperature and heater output.

    Args:
        cryo (Model335): The initialized cryostat controller object.

    Returns:
        dict: Temperature (Celsius) and heater output.
    """
    # Figure out dynamic id (multithreading may cause issues)
    curr_id = 0
    for curr_id in range(10):
        try:
            cryo.get_heater_setup(curr_id)
            break
        except:
            continue
    if curr_id == 9:
        logging.error("Could not identify current heater ID.")
        raise ValueError("Could not identify heater output ID. You may have multiple connections open.")
    try:
        heater_setup = cryo.get_heater_setup(curr_id)
        temperature = cryo.get_all_kelvin_reading()
        heater_output = cryo.get_heater_output(curr_id)
        pid = cryo.get_heater_pid(curr_id)
        heater_range = cryo.get_heater_range(curr_id)

        # Convert heater_range to str TODO: Use enums
        if heater_range == 0:
            heater_range = "off"
        elif heater_range == 1:
            heater_range = "low"
        elif heater_range == 2:
            heater_range = "medium"
        elif heater_range == 3:
            heater_range = "high"

        # Reformat to control message structure
        heater_setup_dict = {
            "output_type": heater_setup["output_type"], # TODO: Resolve type
            "heater_resistance": heater_setup["heater_resistnace"], # Note the spelling mistake, this is the actual key # TODO: Resolve type
            "max_current": heater_setup["max_current"],
            "output_display_mode": heater_setup["output_display_mode"]  # TODO: Resolve type
        }

        temperature_dict = {
            "sensor_1": temperature[0],
            "sensor_2": temperature[1],
            "units": "K"
        }

        heater_output_dict = {
            "output": heater_output,
            "units": "%"
        }

        pid_dict = {
            "gain": pid["gain"],
            "integral": pid["integral"],
            "ramp_rate": pid["ramp_rate"]
        }

        heater_range = {
            "heater_range": heater_range,
        }

        return {
            "heater_setup": heater_setup_dict,
            "temperature": temperature_dict,
            "heater_output": heater_output_dict,
            "pid": pid_dict,
            "heater_range": heater_range,
        }

    except Exception as e:
        print(f"Error fetching status: {e}")
        # raise e
        return None
