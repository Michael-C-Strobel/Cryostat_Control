from lakeshore import Model335

def initialize_connection(port=57600):
    """
    Initializes the connection to the Lake Shore Model 335.
    
    Args:
        port (int): The communication port. Default is 57600.
    
    Returns:
        Model335 instance.
    """
    try:
        cryo = Model335(port)
        return cryo
    except Exception as e:
        print(f"Error initializing connection: {e}")
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
        cryo.set_pid(loop, p_value, i_value, d_value)
        print(f"PID values set: P={p_value}, I={i_value}, D={d_value}")
    except Exception as e:
        print(f"Error setting PID values: {e}")


def set_heater_settings(cryo, heater_resistance, max_current, display_setting):
    """
    Configures the heater settings.

    Args:
        cryo (Model335): The initialized cryostat controller object.
        heater_resistance: Heater resistance setting (e.g., cryo.HeaterResistance.HEATER_25_OHM).
        max_current (float): Maximum heater current.
        display_setting: Heater output display mode (e.g., cryo.HeaterOutputDisplay.POWER).
    """
    try:
        cryo.set_heater_setup_one(heater_resistance, max_current, display_setting)
        print(f"Heater settings applied: Resistance={heater_resistance}, Max Current={max_current}, Display={display_setting}")
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
    try:
        temperature = cryo.get_celsius_reading(0)
        heater_output = cryo.get_heater_output(0)
        return {"temperature": temperature, "heater_output": heater_output}
    except Exception as e:
        print(f"Error fetching status: {e}")
        return None
