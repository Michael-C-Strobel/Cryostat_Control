import asyncio
from lakeshore import Model335
from typing import List, Callable, Optional, Dict
import logging
from status_and_setting_utils import fetch_status
import collections
import json

class TemperatureScheduler:
    def __init__(self, cryo: Model335, heater_output: int, setpoints: List[float], threshold: float = 0.1,
                 sustain_on_exit: bool = False,
                 iv_curve_params: Optional[Dict] = None,
                 on_measurement_complete: Optional[Callable[[float, dict], None]] = None):

        self.cryo = cryo
        self.heater_output = heater_output
        self.setpoints = [float(x) for x in setpoints]
        self.threshold = float(threshold)
        self.current_setpoint_index = 0
        self.running = False
        self.sustain_on_exit = sustain_on_exit
        self.iv_curve_params = iv_curve_params or {}
        self.on_measurement_complete = on_measurement_complete

    async def set_setpoint(self, setpoint: float):
        logging.warning(f"Setting setpoint to {setpoint}")  # Warning as temp to avoid spamming
        self.cryo.set_control_setpoint(self.heater_output, setpoint)

    async def get_temperature(self) -> float:
        curr_status = fetch_status(self.cryo)
        if curr_status is None:
            logging.warning("No status available")
            return None
        return curr_status["temperature"]["sensor_1"]   # For now, hardcode to monitor sensor_1

    async def monitor_temperature(self, on_stable_callback: Optional[Callable[[float], None]] = None):
        """Asynchronously monitor temperature and run a callback when stable.

        If `iv_curve_params` were provided, the scheduler will trigger an IV
        curve measurement at each stable temperature and wait for it to finish
        before moving to the next setpoint. Otherwise it just waits briefly at
        the stable temperature and continues.
        """
        try:
            self.running = True
            while self.current_setpoint_index < len(self.setpoints) and self.running:
                current_setpoint = self.setpoints[self.current_setpoint_index]
                await self.set_setpoint(current_setpoint)

                # Buffer to store historical stability
                required_samples = 400   # 20 seconds at 0.05s sampling
                stability_window = collections.deque(maxlen=required_samples)

                current_temp = float('inf')
                while self.running:
                    _current_temp = await self.get_temperature()
                    if _current_temp is not None:
                        current_temp = _current_temp

                    in_range = abs(current_temp - current_setpoint) <= self.threshold
                    stability_window.append(in_range)

                    if len(stability_window) == required_samples and all(stability_window):
                        logging.warning(f"Temperature {current_temp} is within threshold of setpoint {current_setpoint}")

                        if on_stable_callback:
                            try:
                                await on_stable_callback(current_temp)
                            except Exception as e:
                                logging.error(f"Error during stable-temperature callback: {e}")

                        # If this is the last set point, exit
                        if self.current_setpoint_index == len(self.setpoints) - 1:
                            self.running = False
                            if self.sustain_on_exit:
                                logging.warning("Program Complete. Sustain on exit is enabled. Not turning off heaters.")
                            else:
                                self.cryo.all_heaters_off()
                                logging.warning("Program Complete. All heaters turned off.")

                        break
                    await asyncio.sleep(0.05)  # Avoid tight CPU loop

                self.current_setpoint_index += 1

        except Exception as e:
            self.running = False
            logging.error(f"Error in temperature monitoring: {e}. Scheduler stopped, heaters turned off.")
            self.cryo.all_heaters_off()