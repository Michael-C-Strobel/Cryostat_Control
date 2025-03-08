import dash
from dash import dcc, html
from dash_extensions import WebSocket
import asyncio
import json
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import logging
from datetime import datetime
import pandas as pd
from dash import dash_table

# IV Curve bits
from addons.iv_curve_callbacks import register_callbacks as register_iv_curve_callbacks
from addons.iv_curve import IV_CURVE_CARD

# logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Navbar with Logo
NAVBAR = dbc.Navbar([
        dbc.Row([
            dbc.Col(
                html.A(
                    html.Img(src="assets/Logo.png", width="250px"),
                    href="https://www.maxx-lab.com/"
                ),
            ),
            dbc.Col(dbc.NavbarBrand("Cryostat Control Dashboard", className="ms-2"))
        ], align="center", className="g-0", justify="start"),  # Left-aligned
    ],
    color="light",  # Light theme
    dark=False,     # Dark mode disabled for light theme
    className="mb-4",
)

PARAMETERS = [
    dbc.Row([
        dbc.Label("PID Gain", width=4),
        dbc.Col(
            dbc.Input(
                id="pid-gain", type="number", placeholder="Enter PID Gain"
            ),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Row([
        dbc.Label("PID Integral", width=4),
        dbc.Col(
            dbc.Input(id="pid-integral", type="number", placeholder="Enter PID Integral"),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Row([
        dbc.Label("PID Ramp Rate (Derivative)", width=4),
        dbc.Col(
            dbc.Input(id="pid-ramp-rate", type="number", placeholder="Enter PID Ramp Rate"),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Row([
        dbc.Label("Ramp Rate", width=4),
        dbc.Col(
            dbc.Input(id="ramp-rate", type="number", placeholder="Enter Ramp Rate"),
            width=8,
        ),
    ], className="mb-3", style={"display": "none"}),  # Hidden because it doesn't appear to be settable
    dbc.Row([
        dbc.Label("Heater Resistance", width=4),
        dbc.Col(
            dbc.Input(id="heater-resistance", type="number", placeholder="Enter Heater Resistance"),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Row([
        dbc.Label("Max Current", width=4),
        dbc.Col(
            dbc.Input(id="max-current", type="number", placeholder="Enter Max Current"),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Row([
        dbc.Label("Heater Range", width=4),
        dbc.Col(
            dbc.Select(
                id="heater-range",
                options=[
                    {"label": "Off", "value": "off"},
                    {"label": "Low", "value": "low"},
                    {"label": "Medium", "value": "medium"},
                    {"label": "High", "value": "high"}
                ],
                value="",
            ),
            width=8,
        ),
    ], className="mb-3"),
    dbc.Button("Set Parameters", id="set-parameters-button", color="primary", className="mt-2"),
    dbc.Button("Get Current Values", id="get-current-values-button", color="secondary", className="mt-2 me-2"),
]

df = pd.DataFrame({
    'Temp Value': [293.0, 295.0, 293.0],
})

editable_table = dash_table.DataTable(
    id='editable-table',
    columns=[
        {'name': 'Temp Value', 'id': 'Temp Value', 'editable': True},
    ],
    data=df.to_dict('records'),
    editable=True
)
# Button to add new rows
temperature_schedule_buttons = html.Div([
    dbc.Row([
        dbc.Col(dbc.Button("Add Row", id="add-row-button", color="primary", className="mt-2"), width="auto"),
        dbc.Col(dbc.Button("Delete Row", id="delete-row-button", color="primary", className="mt-2"), width="auto"),  
        dbc.Col(dbc.Button("Run", id="run-button", color="success", className="mt-2"), width="auto"),
        dbc.Col(dbc.Button("Stop", id="stop-button", color="warning", className="mt-2"), width="auto"),
        dbc.Col(dbc.Button("Heater Off", id="heater-off-button", color="danger", className="mt-2"), width="auto"),
    ], className="d-flex justify-content-center")
])

# Callback to add new rows to the table
@app.callback(
    Output('editable-table', 'data', allow_duplicate=True),
    Input('add-row-button', 'n_clicks'),
    State('editable-table', 'data'),
    State('editable-table', 'columns'),
    prevent_initial_call=True
)
def add_row(n_clicks, rows, columns):
    if n_clicks is None:
        return rows
    new_row = {c['id']: '' for c in columns}
    rows.append(new_row)
    return rows

@app.callback(
    Output('editable-table', 'data', allow_duplicate=True),
    Input('delete-row-button', 'n_clicks'),
    State('editable-table', 'data'),
    prevent_initial_call=True
)
def delete_row(n_clicks, rows):
    if n_clicks is None:
        return rows
    if len(rows) > 1:
        rows.pop()
    return rows

temperature_tolerance = html.Div([
    dbc.Row([
        dbc.Label("Temperature Tolerance", width=4),
        dbc.Col(
            dbc.Input(id="temperature-tolerance", type="number", placeholder="Enter Temperature Tolerance", value=0.1),
            width=8,
        ),
        dbc.Tooltip(
            "Tolerance value for measurements to be triggered (measurements will trigger when measured temperature is within +/- threshold).",
            target="temperature-tolerance",
        ),
    ], className="mb-3"),
])

hold_time = html.Div([
    dbc.Row([
        dbc.Label("Hold Time", width=4),
        dbc.Col(
            dbc.Input(id="hold-time", type="number", placeholder="Enter Hold Time", value=60),
            width=8,
        ),
        dbc.Tooltip(
            "Time to hold at each setpoint while taking a measurement.",
            target="hold-time",
        ),
    ], className="mb-3"),
])

sustain_on_end = html.Div([
    dbc.Row([
        dbc.Label("Sustain on End", width=4),
        dbc.Col(
            dbc.Checklist(
                id="sustain-on-end",
                options=[{"label": "Sustain on End", "value": True}],
                value=[],
                switch=True
            ),
            width=8,
        ),
        dbc.Tooltip(
            "If checked, the system will sustain the last setpoint temperature after the schedule ends.",
            target="sustain-on-end",
        ),
    ], className="mb-3"),
])

# Add the button to the layout
editable_table_with_button = html.Div([
    html.H5("Temperature Schedule Options"),
    temperature_tolerance,
    hold_time,
    sustain_on_end,
    editable_table,
    temperature_schedule_buttons
])

INPUT_CARD = dbc.Card([
    dbc.CardHeader("Parameters"),
    dbc.CardBody([
        dbc.Container(PARAMETERS),
        #Horizontal Line
        html.Hr(),
        #Editable Table
        editable_table_with_button,
    ])
])

CONTRIBUTORS_CARD = dbc.Card([
    dbc.CardHeader("Contributors"),
    dbc.CardBody([
            "Michael Strobel - University of California, Riverside", html.Br(),
            "Kaitlyn G. Dold - University of California, Irvine", html.Br(),
            "Dimitri Leo M. Cordova, Ph.D. - University of California, Irvine", html.Br(),
            "Maxx Q. Arguilla, Ph.D. - University of California, Irvine", html.Br(),
    ]),
], style={"margin": "10px"})

CRYOSTAT_MONITORING_CARD = dbc.Card([
    dbc.CardHeader("Cryostat Status"),
    dbc.CardBody([
        html.H5("Temperature (Celsius):"),
        html.Div(id="temperature", className="mb-2"),
        html.H5("Heater Output:"),
        html.Div(id="heater-output", className="mb-2"),
        html.H5("PID Settings:"),
        html.Div(id="pid-settings", className="mb-2"),
        html.H5("Heater Setup:"),
        html.Div(id="heater-setup", className="mb-2"),
        dcc.Graph(id="temperature-plot", config={"displayModeBar": False})
    ])
])

ADDONS = dbc.Card([
    dbc.CardHeader("Addons"),
    dbc.CardBody([
        IV_CURVE_CARD
    ])
])

# Layout with Two Columns
app.layout = html.Div([
    WebSocket(id="ws", url="ws://localhost:8000/ws"),  # Initialize backend connection
    WebSocket(id="set-heater-state-ws", url="ws://localhost:8000/set-heater-state"),
    WebSocket(id="start-temperature-schedule-ws", url="ws://localhost:8000/start-temperature-schedule"),
    WebSocket(id="stop-temperature-schedule-ws", url="ws://localhost:8000/stop-temperature-schedule"),
    WebSocket(id="heaters-off-ws", url="ws://localhost:8000/heaters-off"),
    # Websocket to initialize connection
    WebSocket(id="source-meter-initialize-connection-ws", url="ws://localhost:8001/initialize"),
    # Websocket that lists for current status from source meter
    WebSocket(id="source-meter-status-ws", url="ws://localhost:8001/ws"),
    # Websocket that listens for IV curve data
    WebSocket(id="iv-curve-data-ws", url="ws://localhost:8001/measure_iv_curve"),
    # Websocket that gets options for sourcemeter connections
    # WebSocket(id="sourcemeter-connections-ws", url="ws://localhost:8001/connection_options")
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0), # Update every second
    dcc.Store(id='temperature-history', data=[], storage_type='session'),  # Store historical temperature data
    dcc.Store(id='cryostat-state', data={}),  # Store current cryostat state
    dcc.Store(id='iv-curve-data', data={}),  # Store IV curve data
    NAVBAR,  # Include Navbar at the top
    dbc.Container([
        dbc.Row([
            # Left Column (35%)
            dbc.Col([
                INPUT_CARD,
                CONTRIBUTORS_CARD
            ], width=4),  # 4 out of 12 columns = ~35%

            # Right Column (65%)
            dbc.Col([
                        CRYOSTAT_MONITORING_CARD,
                        ADDONS,
                    ], width=8)  # 8 out of 12 columns = ~65%

        ], className="gx-5")  # Adds spacing between columns
    ], fluid=True)  # Allow container to be responsive
])
    
# Dash callback to update UI when WebSocket message is received
@app.callback(
    Output("cryostat-state", "data"),
    Output("temperature-plot", "figure"),
    Output("temperature-history", "data"),
    Input("interval-component", "n_intervals"),  # Avoids updating on every message
    State("ws", "message"),
    State('temperature-history', 'data')  # Get historical data (temperature and time)
)
def update_status(n_intervals, message, temp_history):
    """Update the status and plot using the WebSocket message data."""
    if not message:
        return {}, {}, []
   
    data = json.loads(message["data"])
    heater_setup = data.get("heater_setup")
    temperature_data = data.get("temperature")
    heater_output_data = data.get("heater_output")
    pid_data = data.get("pid")
    heater_range = data.get("heater_range")

    sensor_1 = temperature_data.get("sensor_1")
    sensor_2 = temperature_data.get("sensor_2")
    assert temperature_data['units'] == "K", "Temperature units are not in Kelvin!"

    heater_output_value = heater_output_data.get("output")

    # Get the current time (timestamp)
    current_time = datetime.now().strftime("%H:%M:%S")

    # Compose dictionary representatoin of the current state
    curr_state = {
        "heater_setup": heater_setup,
        "temperature": temperature_data,
        "heater_output": heater_output_data,
        "pid": pid_data,
        "time": current_time,
        "heater_range": heater_range,
    }

    # logging.debug(f"Setting Current State {curr_state}")

    # Append the temperature and timestamp as a dict
    temp_history.append({
        "sensor_1": sensor_1,
        "sensor_2": sensor_2,
        "time": current_time,
    })

    # Prepare data for plotting
    times = [entry["time"] for entry in temp_history]  # Extract times
    sensor_1_temps = [entry["sensor_1"] for entry in temp_history]  # Extract sensor 1 temperatures
    sensor_2_temps = [entry["sensor_2"] for entry in temp_history]  # Extract sensor 2 temperatures

    valid_indices_1 = [i for i, temp in enumerate(sensor_1_temps) if temp != 0]
    valid_indices_2 = [i for i, temp in enumerate(sensor_2_temps) if temp != 0]

    times_1 = [times[i] for i in valid_indices_1]
    sensor_1_temps = [sensor_1_temps[i] for i in valid_indices_1]

    times_2 = [times[i] for i in valid_indices_2]
    sensor_2_temps = [sensor_2_temps[i] for i in valid_indices_2]

    # Create the plot data list
    plot_data = []
    
    if sensor_1_temps:
        plot_data.append({
            'x': times_1,  # X-axis (timestamps for sensor 1)
            'y': sensor_1_temps,  # Y-axis (temperature data for sensor 1)
            'type': 'line',
            'name': 'Sensor 1 Temperature (K)'
        })
    
    if sensor_2_temps:
        plot_data.append({
            'x': times_2,  # X-axis (timestamps for sensor 2)
            'y': sensor_2_temps,  # Y-axis (temperature data for sensor 2)
            'type': 'line',
            'name': 'Sensor 2 Temperature (K)'
        })

    # Create the plot
    figure = {
        'data': plot_data,
        'layout': {
            'title': 'Temperature Over Time',
            'xaxis': {'title': 'Time'},
            'yaxis': {'title': 'Temperature (Kelvin)'},
            'showlegend': True  # Always show the legend
        }
    }

    return curr_state, figure, temp_history  

@app.callback(
    Output("set-heater-state-ws", "send"),
    Input("set-parameters-button", "n_clicks"),
    State("pid-gain", "value"),
    State("pid-integral", "value"),
    State("pid-ramp-rate", "value"),
    State("ramp-rate", "value"),
    State("heater-resistance", "value"),
    State("max-current", "value"),
    State("heater-range", "value"),
    prevent_initial_call=True
)
def set_heater_state(n_clicks,
                    pid_gain,
                    pid_integral,
                    pid_ramp_rate,
                    ramp_rate,
                    heater_resistance,
                    max_current,
                    heater_range):
    """Send the heater state to the backend."""
    if n_clicks is None:
        return {}
    
    heater_params = {
        "pid_gain": pid_gain,
        "pid_integral": pid_integral,
        "pid_ramp_rate": pid_ramp_rate,
        "ramp_rate": ramp_rate,
        "heater_resistance": heater_resistance,
        "max_current": max_current,
        "heater_range": heater_range
    }
    
    logging.debug(f"Sending heater state: {heater_params}")
    return json.dumps(heater_params)

### Listeners for dashboard fields ###
@app.callback(
    Output("temperature", "children"),
    State("cryostat-state", "data"),
    Input("interval-component", "n_intervals"),
)
def update_temperature(curr_state, n_intervals):
    """Update the temperature display."""
    temperature_data = curr_state.get("temperature")
    if not temperature_data:
        return "No data available"
    sensor_1 = temperature_data.get("sensor_1")
    sensor_2 = temperature_data.get("sensor_2")
    return f"Sensor 1: {sensor_1} °C, Sensor 2: {sensor_2} °C"
    
@app.callback(
    Output("heater-output", "children"),
    State("cryostat-state", "data"),
    Input("interval-component", "n_intervals"),
)
def update_heater_output(curr_state, n_intervals):
    """Update the heater output display."""
    heater_output_data = curr_state.get("heater_output")
    if not heater_output_data:
        return "No data available"
    heater_output_value = heater_output_data.get("output")
    return f"Heater Output: {heater_output_value} %"

@app.callback(
    Output("pid-settings", "children"),
    State("cryostat-state", "data"),
    Input("interval-component", "n_intervals"),
)
def update_pid_settings(curr_state, n_intervals):
    """Update the PID settings display."""
    pid_data = curr_state.get("pid")
    if not pid_data:
        return "No data available"
    pid_settings = f"Gain: {pid_data.get('gain')}, Integral: {pid_data.get('integral')}, Ramp Rate (Derivative): {pid_data.get('ramp_rate')}"
    return pid_settings

@app.callback(
    Output("heater-setup", "children"),
    State("cryostat-state", "data"),
    Input("interval-component", "n_intervals"),
)
def update_heater_setup(curr_state, n_intervals):
    """Update the heater setup display."""
    heater_setup = curr_state.get("heater_setup")
    if not heater_setup:
        return "No data available"
    return f"Heater Setup: {heater_setup}"

@app.callback(
    Output("pid-gain", "value"),
    Output("pid-integral", "value"),
    Output("pid-ramp-rate", "value"),
    Output("heater-resistance", "value"),
    Output("max-current", "value"),
    Output("heater-range", "value"),
    Input("get-current-values-button", "n_clicks"),
    State("cryostat-state", "data"),
    prevent_initial_call=False
)
def update_inputs(n_clicks, curr_state):
    """Update the input fields with the current state when button is pressed."""
    if n_clicks is None:
        return None, None, None, None, None, None

    pid_data = curr_state.get("pid", {})
    heater_setup = curr_state.get("heater_setup", {})

    pid_gain = pid_data.get("gain")
    pid_integral = pid_data.get("integral")
    pid_ramp_rate = pid_data.get("ramp_rate")
    heater_resistance = heater_setup.get("heater_resistance")
    max_current = heater_setup.get("max_current")
    heater_range = curr_state.get("heater_range")

    return pid_gain, pid_integral, pid_ramp_rate, heater_resistance, max_current, heater_range

### Listerners for Temperature Scheduler
@app.callback(
    Output("start-temperature-schedule-ws", "send"),
    Input("run-button", "n_clicks"),
    State("editable-table", "data"),
    State("temperature-tolerance", "value"),
    State("hold-time", "value"),
    State("sustain-on-end", "value"),
    prevent_initial_call=True
)
def start_temperature_schedule(n_clicks, table_data, temperature_tolerance, hold_time, sustain_on_end):
    """Start the temperature schedule based on the table data."""
    if n_clicks is None:
        return {}

    if not isinstance(temperature_tolerance, (int, float)):
        raise ValueError("temperature_tolerance must be a number")

    sustain_on_end = sustain_on_end[0] if sustain_on_end else False
    if not isinstance(sustain_on_end, bool):
        raise ValueError(f"sustain_on_end must be a boolean value, got {sustain_on_end}")

    try:
        setpoints = [float(row["Temp Value"]) for row in table_data if row["Temp Value"]]
    except ValueError:
        raise ValueError("All setpoints must be valid numbers") 

    try:
        hold_time = float(hold_time)
    except ValueError:
        raise ValueError("Hold time must be a valid number")


    threshold = temperature_tolerance

    schedule_data = {
        "setpoints": setpoints,
        "threshold": threshold,
        "sustain": sustain_on_end,
        "hold_time": hold_time,
    }

    logging.info(f"Starting temperature schedule with data: {schedule_data}")

    return json.dumps(schedule_data)

@app.callback(
    Output("stop-temperature-schedule-ws", "send"),
    Input("stop-button", "n_clicks"),
    prevent_initial_call=True
)
def stop_temperature_schedule(n_clicks):
    """Stop the temperature schedule."""
    if n_clicks is None:
        return {}
    
    return json.dumps({"command": "stop_temperature_schedule"})

### Emergency Stop ###
@app.callback(
    Output("heaters-off-ws", "send"),
    Input("heater-off-button", "n_clicks"),
    prevent_initial_call=True
)
def turn_off_heaters(n_clicks):
    """Turn off all heaters."""
    if n_clicks is None:
        return {}
    
    heater_off_command = {
        "command": "turn_off_heaters"
    }
    
    return json.dumps(heater_off_command)

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
    logging.info("Dash Web App is Running at http://localhost:8050/")
