from dash import Input, Output
import dash
import plotly.graph_objs as go
import json
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from dash_extensions import WebSocket
import logging
import asyncio
import websockets
import requests

# Asynchronous WebSocket function for connection
async def connect_to_sourcemeter(adapter):
    url = f"ws://keithley-2400-backend:8001/initialize"
    async with websockets.connect(url) as websocket:
        await websocket.send(json.dumps({"adapter": adapter}))
        response = await websocket.recv()
        response_data = json.loads(response)
        return response_data

# Registering Dash callbacks
def register_callbacks(app):
    logging.warning("Registering Sourcemeter Callbacks")
    
    # Callback for fetching connection options
    @app.callback(
        Output("sourcemeter-adapter-input", "options"),
        Input("sourcemeter-check-connections", "n_clicks"),
    )
    def get_connection_options(n_clicks):
        if n_clicks is None:
            return dash.no_update
        try:
            response = requests.get("http://keithley-2400-backend:8001/connection_options")
            if response.status_code == 200:
                return response.json()["options"]
            else:
                return []  # Return empty if there's an error
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching connection options: {str(e)}")
            return []

    # Callback for initializing the connection to the SourceMeter
    @app.callback(
        Output("sourcemeter-connection-status", "data"),
        Output("sourcemeter-state", "children"),
        Input("sourcemeter-connect-button", "n_clicks"),
        State("sourcemeter-adapter-input", "value"),
        prevent_initial_call=True  # Ensures it only runs when the button is clicked
    )
    def initialize_sourcemeter_connection(n_clicks, adapter):
        if n_clicks is None:
            return dash.no_update, dash.no_update

        # Synchronously execute async WebSocket connection logic
        try:
            result = asyncio.run(connect_to_sourcemeter(adapter))
            logging.warning(f"SourceMeter connection status: {result}")

            # Determine text output based on connection result
            if result.get("status") == "Connection initialized":
                status_text = "Connected to SourceMeter successfully."
            elif result.get("status") == "Failed to connect.":
                status_text = "Failed to connect to SourceMeter."
            else:
                status_text = f"Error: {result.get('detail', 'Unknown error')}"

            return result, status_text

        except Exception as e:
            logging.error(f"Error initializing connection: {str(e)}")
            return {"status": "Error", "detail": str(e)}, f"Error: {str(e)}"

    # Callback for updating the IV curve graph
    @app.callback(
        Output("iv-curve-plot", "figure"),
        Input("iv-curve-data", "data"),
    )
    def update_iv_curve_graph(iv_curve_data):
        if iv_curve_data is None:
            return {}

        temperatures = iv_curve_data.keys()

        fig_iv = go.Figure()
        fig_resistance = go.Figure()

        for temp in temperatures:
            data = iv_curve_data[temp]
            fig_iv.add_trace(go.Scatter(x=data['voltages'], y=data['currents'], mode='lines', name=f'Temp {temp}'))
            resistance = [v / i if i != 0 else None for v, i in zip(data['voltages'], data['currents'])]
            fig_resistance.add_trace(go.Scatter(x=[temp] * len(resistance), y=resistance, mode='lines', name=f'Temp {temp}'))

        if len(fig_iv.data) == 0:
            logging.error("Data is empty in iv curve plot")
            return {}

        return {
            'data': [
                {'type': 'scatter', 'x': fig_iv.data[0].x, 'y': fig_iv.data[0].y, 'name': 'IV Curve'},
                {'type': 'scatter', 'x': fig_resistance.data[0].x, 'y': fig_resistance.data[0].y, 'name': 'Resistance vs Temperature'}
            ],
            'layout': {
                'grid': {'rows': 1, 'columns': 2, 'pattern': 'independent'},
                'annotations': [
                    {'text': 'IV Curve', 'x': 0.25, 'xref': 'paper', 'y': 1.05, 'yref': 'paper', 'showarrow': False},
                    {'text': 'Resistance vs Temperature', 'x': 0.75, 'xref': 'paper', 'y': 1.05, 'yref': 'paper', 'showarrow': False}
                ]
            }
        }

    # WebSocket message handler for handling real-time stability notifications
    @app.callback(
        Output("iv-curve-data", "data"),
        State("iv-curve-data", "data"),
        Input("ws", "message"),  # Listening to messages from the ws WebSocket
        State("sourcemeter-voltage-lower", "value"),
        State("sourcemeter-voltage-upper", "value"),
        State("sourcemeter-voltage-step", "value"),
        prevent_initial_call=True
    )
    def handle_stability_notification(iv_curve_data, message, lb, ub, step):       
        if iv_curve_data is None:
            iv_curve_data = {}

        if not message:
            return iv_curve_data

        # Parse the incoming message
        data = json.loads(message["data"])
        stable_temp = data.get("stable_temperature")
        if stable_temp is not None:
            logging.warning(f"Received stable_temperature notification: {data}")
            # Handle the stable temperature (e.g., updating iv_curve_data or other UI elements)

            # Proceed with IV curve measurements
            voltages = list(range(lb, ub, step))

            # Send voltages for measurement
            try:
                socket = WebSocket(id="iv-curve-data-ws", url="ws://keithley-2400-backend:8001/measure_iv_curve")
                socket.send_text(json.dumps({"voltages": voltages}))
                new_measurement = json.loads(socket.recv())
                iv_curve_data.update(new_measurement)  # Update the iv_curve_data with the new measurement
            except Exception as e:
                logging.error(f"Error during IV curve measurement: {str(e)}")

            return iv_curve_data

    # Callback for the manual IV curve measurement button
    @app.callback(
        Output("iv-curve-data", "data"),
        State("iv-curve-data", "data"),
        Input("manual-iv-curve-btn", "n_clicks"),  # Triggered when the manual button is clicked
        State("sourcemeter-voltage-lower", "value"),
        State("sourcemeter-voltage-upper", "value"),
        State("sourcemeter-voltage-step", "value"),
        prevent_initial_call=True
    )
    def take_manual_iv_curve(iv_curve_data, n_clicks, lb, ub, step):
        if iv_curve_data is None:
            iv_curve_data = {}

        if not n_clicks:
            return iv_curve_data

        # Proceed with IV curve measurements upon button click
        voltages = list(range(lb, ub, step))

        # Send voltages for measurement
        try:
            socket = WebSocket(id="iv-curve-data-ws", url="ws://keithley-2400-backend:8001/measure_iv_curve")
            socket.send_text(json.dumps({"voltages": voltages}))
            new_measurement = json.loads(socket.recv())
            iv_curve_data.update(new_measurement)  # Update the iv_curve_data with the new measurement
        except Exception as e:
            logging.error(f"Error during IV curve measurement: {str(e)}")

        return iv_curve_data