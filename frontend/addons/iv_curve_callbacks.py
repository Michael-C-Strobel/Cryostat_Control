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
from dash.exceptions import PreventUpdate
import numpy as np

# Asynchronous WebSocket function for connection
async def send_websocket_request(command, payload={}):
    """Helper function to send and receive messages via WebSocket."""
    url = "ws://keithley-2400-backend:8001/ws"
    try:
        async with websockets.connect(url) as websocket:
            request = {"command": command, **payload}
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            return json.loads(response)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        return {"status": "Error", "detail": str(e)}

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
        prevent_initial_call=True
    )
    def initialize_sourcemeter_connection(n_clicks, adapter):
        if n_clicks is None:
            return dash.no_update, dash.no_update

        try:
            result = asyncio.run(send_websocket_request("initialize", {"adapter": adapter}))
            logging.warning(f"SourceMeter connection status: {result}")

            status_text = "Connected to SourceMeter successfully." if result.get("status") == "Connection initialized" else "Failed to connect to SourceMeter."
            return result, status_text
        except Exception as e:
            logging.error(f"Error initializing connection: {str(e)}")
            return {"status": "Error", "detail": str(e)}, f"Error: {str(e)}"

    # # Callback for updating the IV curve graph
    # @app.callback(
    #     Output("iv-curve-plot", "figure"),
    #     Input("iv-curve-data", "data"),
    # )
    # def update_iv_curve_graph(iv_curve_data):
    #     if iv_curve_data is None:
    #         return {}

    #     temperatures = iv_curve_data.keys()

    #     fig_iv = go.Figure()
    #     fig_resistance = go.Figure()

    #     for temp in temperatures:
    #         data = iv_curve_data[temp]
    #         fig_iv.add_trace(go.Scatter(x=data['voltages'], y=data['currents'], mode='lines', name=f'Temp {temp}'))
    #         resistance = [v / i if i != 0 else None for v, i in zip(data['voltages'], data['currents'])]
    #         fig_resistance.add_trace(go.Scatter(x=[temp] * len(resistance), y=resistance, mode='lines', name=f'Temp {temp}'))

    #     if len(fig_iv.data) == 0:
    #         logging.error("Data is empty in iv curve plot")
    #         return {}

    #     return {
    #         'data': [
    #             {'type': 'scatter', 'x': fig_iv.data[0].x, 'y': fig_iv.data[0].y, 'name': 'IV Curve'},
    #             {'type': 'scatter', 'x': fig_resistance.data[0].x, 'y': fig_resistance.data[0].y, 'name': 'Resistance vs Temperature'}
    #         ],
    #         'layout': {
    #             'grid': {'rows': 1, 'columns': 2, 'pattern': 'independent'},
    #             'annotations': [
    #                 {'text': 'IV Curve', 'x': 0.25, 'xref': 'paper', 'y': 1.05, 'yref': 'paper', 'showarrow': False},
    #                 {'text': 'Resistance vs Temperature', 'x': 0.75, 'xref': 'paper', 'y': 1.05, 'yref': 'paper', 'showarrow': False}
    #             ]
    #         }
    #     }

    @app.callback(
        Output("iv-curve-plot", "figure"),
        Input("iv-curve-data", "data"),
    )
    def update_iv_curve_graph(iv_curve_data):
        if iv_curve_data is None:
            return go.Figure()

        fig_iv = go.Figure()
        fig_resistance = go.Figure()

        logging.warning(f"Recieved the following input data {iv_curve_data}")

        for temp, data in iv_curve_data.items():
            fig_iv.add_trace(go.Scatter(x=data['voltages'], y=data['currents'], mode='lines', name=f'Temp {temp}'))
            resistance = [v / i if i != 0 else None for v, i in zip(data['voltages'], data['currents'])]
            fig_resistance.add_trace(go.Scatter(x=[temp] * len(resistance), y=resistance, mode='lines', name=f'Temp {temp}'))

        # Update layout with x and y axis labels
        fig_iv.update_layout(
            xaxis_title="Voltage (V)",  # Label for x-axis
            yaxis_title="Current (A)",  # Label for y-axis
            title="IV Curve"  # Optional: Title for the figure
        )

        return fig_iv

    # WebSocket message handler for handling real-time stability notifications
    @app.callback(
        Output("iv-curve-data", "data", allow_duplicate=True),
        State("iv-curve-data", "data"),
        Input("ws", "message"),  # Listening to messages from the WebSocket
        State("sourcemeter-voltage-lower", "value"),
        State("sourcemeter-voltage-upper", "value"),
        State("sourcemeter-voltage-step", "value"),
        prevent_initial_call=True
    )
    def handle_stability_notification(iv_curve_data, message, lb, ub, step):
        if iv_curve_data is None:
            iv_curve_data = {}

        if not message:
            raise dash.exceptions.PreventUpdate

        # Parse incoming WebSocket message
        data = json.loads(message["data"])
        stable_temp = data.get("stable_temperature")
        
        if stable_temp is not None:
            logging.warning(f"Received stable_temperature notification: {data}")

            if step == 0.0:
                logging.error("SourceMeter Voltage Step was Zero")
                raise dash.exceptions.PreventUpdate

            # Define voltage sweep range
            voltages = list(np.arange(float(lb), float(ub), float(step)))

            # Send WebSocket request for IV curve measurement
            try:
                result = asyncio.run(send_websocket_request("measure_iv_curve", {
                    "start_voltage": voltages[0],
                    "stop_voltage": voltages[-1],
                    "step_voltage": step,
                    "compliance_current": 0.1,  # Default compliance current TODO
                    "source_voltage_range": 20  # Default voltage range TODO
                }))

                if "iv_curve" in result:
                    iv_curve_data['stable_temp'] = result["iv_curve"]
                else:
                    logging.error(f"IV curve measurement error: {result}")
                    raise dash.exceptions.PreventUpdate

            except Exception as e:
                logging.error(f"Error during IV curve measurement: {str(e)}")
                raise dash.exceptions.PreventUpdate

            return iv_curve_data

        raise dash.exceptions.PreventUpdate

    # Callback for the manual IV curve measurement button
    @app.callback(
        Output("iv-curve-data", "data", allow_duplicate=True),
        State("iv-curve-data", "data"),
        Input("manual-iv-curve-btn", "n_clicks"),
        State("sourcemeter-voltage-lower", "value"),
        State("sourcemeter-voltage-upper", "value"),
        State("sourcemeter-voltage-step", "value"),
        State("sourcemeter-compliance-current", "value"),
        State("sourcemeter-voltage-range", "value"),
        prevent_initial_call=True
    )
    def take_manual_iv_curve(iv_curve_data, n_clicks, lb, ub, step, compliance_current, source_voltage_range):
        if not n_clicks:
            raise dash.exceptions.PreventUpdate

        if iv_curve_data is None:
            iv_curve_data = {}

        if step == 0.0:
            logging.error("SourceMeter Voltage Step was Zero")
            raise dash.exceptions.PreventUpdate

        voltages = list(np.arange(float(lb), float(ub), float(step)))

        try:
            result = asyncio.run(send_websocket_request("measure_iv_curve", {
                "start_voltage": voltages[0],
                "stop_voltage": voltages[-1],
                "step_voltage": step,
                "compliance_current": 0.1,
                "source_voltage_range": 20
            }))
            
            if "iv_curve" in result:
                iv_curve_data['Manual Curve'] = result["iv_curve"]
            else:
                logging.error(f"IV curve measurement error: {result}")
                return dash.no_update
        except Exception as e:
            logging.error(f"Error during IV curve measurement: {str(e)}")
            return dash.no_update

        return iv_curve_data