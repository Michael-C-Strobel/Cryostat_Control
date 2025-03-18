## Cryostat Controller
This repository contains the code to run a cryostat controller, in combination with other instruments.

Currently cryostat controllers are:
- LakeShore Model 355

Currently Supported Addons Are:
- IV-Curves: Keithley 2400 Source Meter

### Requirements
- Linux
- Docker with Root Privlage
- Git

To setup an IV-Curve experiment, do the following:
1. ssh into the computer controlling the instrument
1. Setup a tunnel for the frontend port (8050) to local. It is highly recomended to use VSCode which will do this automatically
1. Launch the app from within the directory
```
make server-compose-interactive
```
At this point the dashboard should be available at [http://localhost:8050/](http://localhost:8050/).
Note: If using VSCode, your port may vary, check the relevant links in the ports tab in the console area.

### Todo list:
- [ ] Cleanup Connection Exceptions
- [ ] Option to Sweep Current Rather than Voltage
- [ ] Option to launch without Keithley
- [ ] Data Download Buttons
- [ ] Persistence without session
- [ ] Companion App to Automatically Port Forward and Open Interface
- [ ] Addition Add-Ons
- [ ] Expose remaining Keithley 2400 Options to interface (`num_averages`, `nplc`)
- [ ] Dynamically hold Cryostat until measurement is complete (currently holds for 60 seconds regardless)