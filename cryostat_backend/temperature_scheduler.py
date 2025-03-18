import asyncio
from lakeshore import Model335
from typing import List, Callable
import logging
from status_and_setting_utils import fetch_status

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
        return fetch_status(self.cryo)["temperature"]["sensor_1"]   # For now, hardcode to monitor sensor_1

    async def monitor_temperature(self, callback: Callable[[float], None]):
        """Asynchronously monitor temperature, call `callback` when stable."""
        try:
            self.running = True
            while self.current_setpoint_index < len(self.setpoints) and self.running:
                current_setpoint = self.setpoints[self.current_setpoint_index]
                await self.set_setpoint(current_setpoint)

                while self.running:
                    logging.warning("Checking Current T in loop")
                    current_temp = await self.get_temperature()
                    logging.warning(f"Got current temp {current_temp}")
                    if abs(current_temp - current_setpoint) <= self.threshold:
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
                    await asyncio.sleep(0.01)  # Avoid tight CPU loop

                self.current_setpoint_index += 1

        except Exception as e:
            self.running = False
            cryo.all_heaters_off()
            logging.error(f"Error in temperature monitoring: {e}")