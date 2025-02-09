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
        html.Div(id="heater-output"),
        dcc.Graph(id="temperature-plot", config={"displayModeBar": False})
    ])
])

# Layout with Two Columns
app.layout = html.Div([
    WebSocket(id="ws", url="ws://localhost:8000/ws"),  # Initialize backend connection
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0), # Update every second
    dcc.Store(id='temperature-history', data=[]),  # Store historical temperature data
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
    Output("temperature", "children"),
    Output("heater-output", "children"),
    Output("temperature-plot", "figure"),
    Output("temperature-history", "data"),
    Input("interval-component", "n_intervals"),  # Avoids updating on every message
    State("ws", "message"),
    State('temperature-history', 'data')  # Get historical data (temperature and time)
)
def update_status(n_intervals, message, temp_history):
    """Update the status and plot using the WebSocket message data."""
    if not message:
        return "Unknown", "Unknown", {}, []
   
    data = json.loads(message["data"])
    temperature = data.get("temperature", "Unknown")
    heater_output = data.get("heater_output", "Unknown")

    # Get the current time (timestamp)
    current_time = datetime.now().strftime("%H:%M:%S")

    # Append the temperature and timestamp as a dict
    temp_history.append({
        "temperature": temperature,
        "time": current_time
    })

    # Prepare data for plotting
    times = [entry["time"] for entry in temp_history]  # Extract times
    temperatures = [entry["temperature"] for entry in temp_history]  # Extract temperatures

    # Create the plot
    figure = {
        'data': [
            {
                'x': times,  # X-axis (timestamps)
                'y': temperatures,  # Y-axis (temperature data)
                'type': 'line',
                'name': 'Temperature'
            }
        ],
        'layout': {
            'title': 'Temperature Over Time',
            'xaxis': {'title': 'Time'},
            'yaxis': {'title': 'Temperature (Celsius)'}
        }
    }

    return temperature, heater_output, figure, temp_history  
    

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
    logging.info("Dash Web App is Running at http://localhost:8050/")
