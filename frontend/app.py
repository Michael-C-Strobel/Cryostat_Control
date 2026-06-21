import dash
from dash import dcc, html
import json
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import logging
from datetime import datetime
import pandas as pd
from dash import dash_table
from dash_extensions.enrich import DashProxy, BlockingCallbackTransform
import time
import threading
import requests

# IV Curve bits
from addons.iv_curve_callbacks import register_callbacks as register_iv_curve_callbacks
from addons.iv_curve import IV_CURVE_CARD

# logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)

# -----------------------------------------------------------------------------
# Server-side bridge to cryostat-backend
# -----------------------------------------------------------------------------
# The frontend talks to the backend inside the Docker network via REST.
# The user's browser only needs access to the Dash UI on port 8050.
# -----------------------------------------------------------------------------

BACKEND_HTTP_URL = "http://cryostat-backend:8000"
LATEST_BACKEND_MESSAGE = None
_BACKEND_LOCK = threading.Lock()

# Reduce library debug noise in the container logs.
logging.getLogger("urllib3").setLevel(logging.WARNING)


def _backend_status_polling_thread():
    """Poll the backend /status endpoint and store the latest message."""
    global LATEST_BACKEND_MESSAGE
    url = f"{BACKEND_HTTP_URL}/status"
    last_error_time = 0
    error_log_interval_sec = 5
    while True:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            with _BACKEND_LOCK:
                LATEST_BACKEND_MESSAGE = data
        except Exception as e:
            now = time.time()
            if now - last_error_time > error_log_interval_sec:
                logging.error(f"Backend status poll error: {e}. Suppressing further errors for {error_log_interval_sec}s...")
                last_error_time = now
        time.sleep(0.25)


# Start the background poller as soon as this module is imported.
_backend_status_thread = threading.Thread(target=_backend_status_polling_thread, daemon=True)
_backend_status_thread.start()


def send_backend_command(endpoint: str, payload: dict):
    """Send a command to a backend REST endpoint."""
    url = f"{BACKEND_HTTP_URL}/{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error sending command to {url}: {e}")
        return {"status": "Error", "detail": str(e)}


# Initialize Dash app
app = DashProxy(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
                transforms=[BlockingCallbackTransform(timeout=60)])

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
    dbc.Button("Reset to Defaults", id="reset-parameters-button", color="info", className="mt-2"),
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

sustain_on_end = html.Div([
    dbc.Row([
        dbc.Label("Sustain on End", width=4),
        dbc.Col(
            dbc.Checklist(
                id="sustain-on-end",
                options=[{"label": None, "value": True}],
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
        html.H5("Temperature:"),
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
        IV_CURVE_CARD,
        html.Div(id="iv-curve-debug"),
        html.Div(id="iv-curve-debug2"),
        html.Button("Test Update", id="test-btn"),
    ])
])
register_iv_curve_callbacks(app)

# Layout with Two Columns
app.layout = html.Div([
    # Hidden divs used as dummy outputs for command callbacks.
    # Dash requires unique outputs, so each command callback gets its own.
    html.Div(id="set-heater-state-status", style={"display": "none"}),
    html.Div(id="start-schedule-status", style={"display": "none"}),
    html.Div(id="stop-schedule-status", style={"display": "none"}),
    html.Div(id="heaters-off-status", style={"display": "none"}),
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0), # Update every second
    dcc.Store(id='temperature-history', data=[], storage_type='session'),  # Store historical temperature data  # TODO: Set to local for all
    dcc.Store(id='cryostat-state', data=dict(), storage_type='session'),  # Store current cryostat state
    dcc.Store(id='iv-curve-data', data=dict(), storage_type='session'),  # Store IV curve data
    dcc.Store(id="sourcemeter-task-id", data="", storage_type='memory'), # Store currently running communication tasks with SourceMeter
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
    
# Dash callback to update UI with the latest backend status
@app.callback(
    Output("cryostat-state", "data"),
    Output("temperature-plot", "figure"),
    Output("temperature-history", "data"),
    Input("interval-component", "n_intervals"),  # Poll every second
    State('temperature-history', 'data')  # Get historical data (temperature and time)
)
def update_status(n_intervals, temp_history):
    """Update the status and plot using the latest backend status poll."""

    global LATEST_BACKEND_MESSAGE

    if not temp_history:
        temp_history = []

    with _BACKEND_LOCK:
        data = LATEST_BACKEND_MESSAGE

    if not data:
        return {}, {}, temp_history
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

    # Append the temperature and timestamp as a dict
    temp_history.append({
        "sensor_1": sensor_1,
        "sensor_2": sensor_2,
        "time": current_time,
    })

    # Limit history to last 1000 entries to avoid memory issues
    if len(temp_history) > 1000:
        temp_history = temp_history[-1000:]

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
    Output("set-heater-state-status", "children"),
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
        return dash.no_update

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
    send_backend_command("set-heater-state", heater_params)
    return f"Heater state sent at {datetime.now()}"  # dummy output for hidden div

### Listeners for dashboard fields ###
@app.callback(
    Output("temperature", "children"),
    Input("interval-component", "n_intervals"),
        State("cryostat-state", "data"),
)
def update_temperature(n_intervals, curr_state):
    """Update the temperature display."""
    temperature_data = curr_state.get("temperature")
    if not temperature_data:
        return "No data available"
    sensor_1 = temperature_data.get("sensor_1")
    sensor_2 = temperature_data.get("sensor_2")
    return f"Sensor 1: {sensor_1} °K, Sensor 2: {sensor_2} °K"
    
@app.callback(
    Output("heater-output", "children"),
    Input("interval-component", "n_intervals"),
    State("cryostat-state", "data"),
)
def update_heater_output(n_intervals, curr_state):
    """Update the heater output display."""
    heater_output_data = curr_state.get("heater_output")
    if not heater_output_data:
        return "No data available"
    heater_output_value = heater_output_data.get("output")
    return f"Heater Output: {heater_output_value} %"

@app.callback(
    Output("pid-settings", "children"),
    Input("interval-component", "n_intervals"),
    State("cryostat-state", "data"),
)
def update_pid_settings(n_intervals, curr_state):
    """Update the PID settings display."""
    pid_data = curr_state.get("pid")
    if not pid_data:
        return "No data available"
    pid_settings = f"Gain: {pid_data.get('gain')}, Integral: {pid_data.get('integral')}, Ramp Rate (Derivative): {pid_data.get('ramp_rate')}"
    return pid_settings

@app.callback(
    Output("heater-setup", "children"),
    Input("interval-component", "n_intervals"),
    State("cryostat-state", "data"),
)
def update_heater_setup(n_intervals, curr_state):
    """Update the heater setup display."""
    heater_setup = curr_state.get("heater_setup")
    if not heater_setup:
        return "No data available"
    return f"Heater Setup: {heater_setup}"

@app.callback(
    Output("pid-gain", "value", allow_duplicate=True),
    Output("pid-integral", "value", allow_duplicate=True),
    Output("pid-ramp-rate", "value", allow_duplicate=True),
    Output("heater-resistance", "value", allow_duplicate=True),
    Output("max-current", "value", allow_duplicate=True),
    Output("heater-range", "value", allow_duplicate=True),
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
    heater_range = curr_state.get("heater_range", {}).get("heater_range")

    return pid_gain, pid_integral, pid_ramp_rate, heater_resistance, max_current, heater_range

@app.callback(
    Output("pid-gain", "value", allow_duplicate=True),
    Output("pid-integral", "value", allow_duplicate=True),
    Output("pid-ramp-rate", "value", allow_duplicate=True),
    Output("heater-resistance", "value", allow_duplicate=True),
    Output("max-current", "value", allow_duplicate=True),
    Output("heater-range", "value", allow_duplicate=True),
    Input("reset-parameters-button", "n_clicks"),
    prevent_initial_call=True
)
def reset_parameters(n_clicks):
    """Reset parameter inputs to safe default values."""
    if n_clicks is None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    return 60, 25, 0, 2, 1, "off"

### Listerners for Temperature Scheduler
@app.callback(
    Output("start-schedule-status", "children"),
    Input("run-button", "n_clicks"),
    State("editable-table", "data"),
    State("temperature-tolerance", "value"),
    State("sustain-on-end", "value"),
    State("iv-curve-type", "value"),
    State("sourcemeter-voltage-lower", "value"),
    State("sourcemeter-voltage-upper", "value"),
    State("sourcemeter-voltage-step", "value"),
    State("sourcemeter-compliance-current", "value"),
    State("sourcemeter-voltage-range", "value"),
    State("sourcemeter-current-lower", "value"),
    State("sourcemeter-current-upper", "value"),
    State("sourcemeter-current-step", "value"),
    State("sourcemeter-compliance-voltage", "value"),
    State("sourcemeter-current-range", "value"),
    prevent_initial_call=True
)
def start_temperature_schedule(
    n_clicks, table_data, temperature_tolerance, sustain_on_end,
    sweep_type,
    v_lb, v_ub, v_step, compliance_current, voltage_range,
    c_lb, c_ub, c_step, compliance_voltage, current_range,
):
    """Start the temperature schedule based on the table data."""
    if n_clicks is None:
        return dash.no_update

    if not isinstance(temperature_tolerance, (int, float)):
        raise ValueError("temperature_tolerance must be a number")

    sustain_on_end = sustain_on_end[0] if sustain_on_end else False
    if not isinstance(sustain_on_end, bool):
        raise ValueError(f"sustain_on_end must be a boolean value, got {sustain_on_end}")

    try:
        setpoints = [float(row["Temp Value"]) for row in table_data if row["Temp Value"]]
    except ValueError:
        raise ValueError("All setpoints must be valid numbers")

    threshold = temperature_tolerance

    schedule_data = {
        "setpoints": setpoints,
        "threshold": threshold,
        "sustain": sustain_on_end,
    }

    if sweep_type in ("voltage_sweep", "current_sweep"):
        if sweep_type == "voltage_sweep":
            schedule_data["iv_curve_params"] = {
                "sweep_type": "voltage_sweep",
                "voltage_lower": v_lb,
                "voltage_upper": v_ub,
                "voltage_step": v_step,
                "compliance_current": compliance_current,
                "voltage_range": voltage_range,
            }
        else:
            schedule_data["iv_curve_params"] = {
                "sweep_type": "current_sweep",
                "current_lower": c_lb,
                "current_upper": c_ub,
                "current_step": c_step,
                "compliance_voltage": compliance_voltage,
                "current_range": current_range,
            }

    logging.info(f"Starting temperature schedule with data: {schedule_data}")
    send_backend_command("start-temperature-schedule", schedule_data)
    return f"Temperature schedule started at {datetime.now()}"  # dummy output for hidden div

@app.callback(
    Output("stop-schedule-status", "children"),
    Input("stop-button", "n_clicks"),
    prevent_initial_call=True
)
def stop_temperature_schedule(n_clicks):
    """Stop the temperature schedule."""
    if n_clicks is None:
        return dash.no_update

    send_backend_command("stop-temperature-schedule", {"command": "stop_temperature_schedule"})
    return f"Temperature schedule stopped at {datetime.now()}"  # dummy output for hidden div

### Emergency Stop ###
@app.callback(
    Output("heaters-off-status", "children"),
    Input("heater-off-button", "n_clicks"),
    prevent_initial_call=True
)
def turn_off_heaters(n_clicks):
    """Turn off all heaters."""
    if n_clicks is None:
        return dash.no_update

    send_backend_command("heaters-off", {"command": "turn_off_heaters"})
    return f"Heaters off command sent at {datetime.now()}"  # dummy output for hidden div

# Run the app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
    logging.info("Dash Web App is Running at http://localhost:8050/")
