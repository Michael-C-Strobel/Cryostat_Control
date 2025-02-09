import dash
from dash import dcc, html
from dash_extensions import WebSocket
import asyncio
import json
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

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

INPUT_CARD = dbc.Card([
    dbc.CardHeader("Parameters"),
    dbc.CardBody("Input placeholder here")
])

CONTRIBUTORS_CARD = dbc.Card([
    dbc.CardHeader("Contributors"),
    dbc.CardBody([
            "Michael Strobel - University of California, Riverside", html.Br(),
            "Kaitlyn G. Dold - University of California, Irvine", html.Br(),
            "Dimitri Leo M. Cordova, Ph.D. - University of California, Irvine", html.Br(),
            "Maxx Q. Arguilla, Ph.D. - University of California, Irvine", html.Br(),
    ])
])

MONITORING_CARD = dbc.Card([
    dbc.CardHeader("Current Status"),
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

# Layout with Two Columns
app.layout = html.Div([
    WebSocket(id="ws", url="ws://localhost:8000/ws"),  # Initialize backend connection
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0), # Update every second
    dcc.Store(id='temperature-history', data=[], storage_type='session'),  # Store historical temperature data
    dcc.Store(id='cryostat-state', data={}),  # Store current cryostat state
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
                        MONITORING_CARD,
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
    }

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

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
    logging.info("Dash Web App is Running at http://localhost:8050/")
