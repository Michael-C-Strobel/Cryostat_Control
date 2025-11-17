import asyncio
from lakeshore import Model335
from typing import List, Callable
import logging
from status_and_setting_utils import fetch_status
import collections

class TemperatureScheduler:
    def __init__(self, cryo: Model335, heater_output: int, setpoints: List[float], threshold: float = 0.1,
                 hold_time: float = 60,
                 sustain_on_exit: bool = False):
        
        self.cryo = cryo
        self.heater_output = heater_output
        self.setpoints = [float(x) for x in setpoints]
        self.threshold = float(threshold)
        self.current_setpoint_index = 0
        self.running = False
        self.hold_time = hold_time
        self.sustain_on_exit = sustain_on_exit

    async def set_setpoint(self, setpoint: float):
        logging.warning(f"Setting setpoint to {setpoint}")  # Warning as temp to avoid spamming
        self.cryo.set_control_setpoint(self.heater_output, setpoint)

    async def get_temperature(self) -> float:
        curr_status = fetch_status(self.cryo)
        if curr_status is None:
            logging.warning("No status available")
            return None
        return curr_status["temperature"]["sensor_1"]   # For now, hardcode to monitor sensor_1

    async def monitor_temperature(self, callback: Callable[[float], None]):
        """Asynchronously monitor temperature, call `callback` when stable."""
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
                    # logging.warning("Checking Current T in loop")
                    _current_temp = await self.get_temperature()    # This logic basically means "if there's an error, keep monitoring and wait"
                    if _current_temp is not None:
                        current_temp = _current_temp

                    in_range = abs(current_temp - current_setpoint) <= self.threshold
                    stability_window.append(in_range)
                        
                    # logging.warning(f"Got current temp {current_temp}")
                    if len(stability_window) == required_samples and all(stability_window):
                        logging.warning(f"Temperature {current_temp} is within threshold of setpoint {current_setpoint}")
                        callback(current_temp)  # Notify via callback
                        await asyncio.sleep(self.hold_time)  # Hold for the specified time to get a measurement

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