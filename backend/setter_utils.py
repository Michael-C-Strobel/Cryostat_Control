from lakeshore import Model335
import logging
from typing import List, Tuple

def set_curve(cryo:Model335, data:List[Tuple[float, float, float]]):
    """
    Sets the temperature curve.

    Args:
        cryo (Model335): The initialized cryostat controller object.
        data (List(Tuple[float, float, float])): The temperature curve data. 
        (sensor_units: float, temp_value: float, curvature_value: float (optional)).
    """
    try:
        cryo.set_curve(0, data) # Hardcoded to set curve 0
        logging.info(f"Temperature curve set: {data}")
    except Exception as e:
        logging.error(f"Error setting temperature curve: {e}")
    
def get_curve(cryo:Model335,):
    """Gets the current temperature curve

    Args:
        cryo (Model335):
    """
    return cryo.get_curve(0)