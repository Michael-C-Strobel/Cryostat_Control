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
import base64
import traceback
import os

from .iv_curve_celery.tasks import run_sourcemeter_measurement
from .iv_curve_celery.celery_app import celery_app
from celery.result import AsyncResult
from celery.signals import task_success
import redis

REDIS_URL = os.getenv("CELERY_BROKER_URL")
redis_client = redis.Redis.from_url(REDIS_URL)

if not REDIS_URL:
    raise ValueError("CELERY_BROKER_URL must be set in environment variables.")

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
        if len(iv_curve_data) == 0 or iv_curve_data is None:
            return go.Figure()

        fig_iv = go.Figure()
        fig_resistance = go.Figure()

        logging.warning(f"Recieved the following input data {iv_curve_data}")

        iv_curve_data = iv_curve_data[0]

        for temp, data in iv_curve_data.items():
            logging.warning(f"Plotting temp {temp}, data {data}")
            fig_iv.add_trace(go.Scatter(x=data['voltages'], y=data['currents'], mode='lines', name=f'Temp {temp}'))
            resistance = [v / i if i != 0 and ((not isinstance(i, str)) and (not isinstance(v, str)))else None for v, i in zip(data['voltages'], data['currents'])]
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
        Output("sourcemeter-task-id", "data"),
        Input("ws", "message"),
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
        prevent_initial_call=True,
    )
    def handle_stability_notification(
        message, sweep_type,
        v_lb, v_ub, v_step, compliance_current, voltage_range,
        c_lb, c_ub, c_step, compliance_voltage, current_range,
    ):
        if not message:
            return dash.no_update

        logging.info(f"handle_stability_notification is polling with message: {message}")
        try:
            data = json.loads(message["data"])
            if "stable_temperature" not in data:
                return dash.no_update
            stable_temp = data["stable_temperature"]
            logging.info(f"Received stable_temperature notification: {data}")

            if sweep_type == "voltage_sweep":
                if v_step == 0.0:
                    logging.error("Voltage Step was Zero")
                    return dash.no_update
                voltages = list(np.arange(float(v_lb), float(v_ub), float(v_step)))
                payload = {
                    "key": str(stable_temp),
                    "type": "voltage_sweep",
                    "start_voltage": voltages[0],
                    "stop_voltage": voltages[-1],
                    "step_voltage": v_step,
                    "compliance_current": compliance_current,
                    "source_voltage_range": voltage_range,
                }
            elif sweep_type == "current_sweep":
                if c_step == 0.0:
                    logging.error("Current Step was Zero")
                    return dash.no_update
                currents = list(np.arange(float(c_lb), float(c_ub), float(c_step)))
                payload = {
                    "key": str(stable_temp),
                    "type": "current_sweep",
                    "start_current": currents[0],
                    "stop_current": currents[-1],
                    "step_current": c_step,
                    "compliance_voltage": compliance_voltage,
                    "source_current_range": current_range,
                }
            else:
                logging.error(f"Unknown sweep type: {sweep_type}")
                return dash.no_update

            task = run_sourcemeter_measurement.apply_async(args=["measure_iv_curve", payload])
            logging.warning(f"[handle_stability_notification] Queued task ID: {task.id}")
            return str(task.id)

        except Exception as e:
            logging.error(f"Error queuing measurement task:\n{e}")
            return dash.no_update
    
    # This is pretty janky, in principle the results could be overwritten by the time this runs
    # But our interval is faster than the SourceMeter can run.
    # When the dcc.Store + WebSocket bug is resolved, this should be deprecated
    @app.callback(
        Output("iv-curve-data", "data"),
        Input("interval-component", "n_intervals"),
        State("iv-curve-data", "data"),
        prevent_initial_call=True,
    )
    def poll_for_completed_results(_, iv_curve_data):
        # Try popping from Redis
        raw = redis_client.lpop("sourcemeter:results")

        if not raw:
            logging.info("[Polling] No completed task result found in Redis")
            return dash.no_update

        try:
            payload = json.loads(raw)
            result = payload["result"]
            logging.info(f"[Polling] Processing result from Redis: {result}")
        except Exception as e:
            logging.error(f"[Polling] Error parsing task result: {e}")
            return dash.no_update

        if result.get("key") == "manual_curve":
            return dash.no_update
        elif "iv_curve" in result:
            stable_temp = result.get("key", "unknown")

            # Ensure dict shape
            if iv_curve_data is None:
                iv_curve_data = [{}]
            iv_curve_data = iv_curve_data.copy()
            if isinstance(iv_curve_data, list):
                iv_curve_data = iv_curve_data[0]

            iv_curve_data[str(stable_temp)] = result["iv_curve"]
            return [iv_curve_data]
        else:
            logging.error(f"[Polling] Unexpected result format: {result}")

        return dash.no_update

    # # Callback for the manual IV curve measurement button
    # @app.callback(
    #     Output("iv-curve-data", "data", allow_duplicate=True),
    #     State("iv-curve-data", "data"),
    #     Input("manual-iv-curve-btn", "n_clicks"),
    #     State("sourcemeter-voltage-lower", "value"),
    #     State("sourcemeter-voltage-upper", "value"),
    #     State("sourcemeter-voltage-step", "value"),
    #     State("sourcemeter-compliance-current", "value"),
    #     State("sourcemeter-voltage-range", "value"),
    #     prevent_initial_call=True
    # )
    # def take_manual_iv_curve(iv_curve_data, n_clicks, lb, ub, step, compliance_current, source_voltage_range):
    #     if not n_clicks:
    #         dash.no_update

    #     if iv_curve_data is None:
    #         iv_curve_data = {}

    #     # Copy so dash will detect changes
    #     iv_curve_data = iv_curve_data.copy()

    #     if step == 0.0:
    #         logging.error("SourceMeter Voltage Step was Zero")
    #         dash.no_update

    #     voltages = list(np.arange(float(lb), float(ub), float(step)))

    #     try:
    #         result = asyncio.run(send_websocket_request("measure_iv_curve", {
    #             "key": "manual_curve",
    #             "start_voltage": voltages[0],
    #             "stop_voltage": voltages[-1],
    #             "step_voltage": step,
    #             "compliance_current": 0.1,
    #             "source_voltage_range": 20
    #         }))
            
    #         if "iv_curve" in result:
    #             iv_curve_data['Manual Curve'] = result["iv_curve"]
    #             logging.info(f"Updating curve using manual data: {iv_curve_data['Manual Curve'] }")
    #         else:
    #             logging.error(f"IV curve measurement error: {result}")
    #             return dash.no_update
    #     except Exception as e:
    #         logging.error(f"Error during IV curve measurement: {str(e)}")
    #         return dash.no_update

    #     return iv_curve_data

    @app.callback(
        Output("iv-curve-download", "data"),  # This triggers the download
        Input("iv-curve-download-button", "n_clicks"),
        State("iv-curve-data", "data"),  # The data you want to download
    )
    def download_iv_curve_data(n_clicks, iv_curve_data):
        if n_clicks is None:
            return dash.no_update  # Don't do anything if no click

        if iv_curve_data is None:
            iv_curve_data = "No Cruve Data"

        print("iv_curve_data in download callback", iv_curve_data, flush=True)
        
        # Convert the IV curve data to JSON with indentation for readability
        iv_curve_json = json.dumps(iv_curve_data, indent=4)
        
        # Return the JSON as plain text with the appropriate filename
        return dict(content=iv_curve_json, filename="iv_curve_data.json")

    @app.callback(Output("iv-curve-debug", "children"), 
                    Input("iv-curve-data", "data"),
                    Input("iv-curve-data", "data"),
                    )
    def show_data(data, data_state):
        if len(data) == 0 or not data:
            return ""

        data = data[0]
        data_state = data_state[0]
        a = f"Current keys data: {list(data.keys())}" if isinstance(data, dict) else str(data)
        b = f"Current keys data_state: {list(data_state.keys())}" if isinstance(data_state, dict) else str(data_state)

        return f"{a} \n {b}"

    @app.callback(Output("iv-curve-debug2", "children"), 
                    Input("sourcemeter-task-id", "data"),
    )
    def show_task_id(task_id):
        return f"Current task ID: {task_id}"

    # @app.callback(
    #     Output("sourcemeter-task-id", "data"),
    #     Input("test-btn", "n_clicks"),
    #     prevent_initial_call=True,
    # )
    # def test_update(n_clicks):
    #     return f"task-id-{n_clicks}"

    @app.callback(
        Output("iv-curve-data", "data", allow_duplicate=True),
        Input("iv-curve-clear-data", "n_clicks"),
        prevent_initial_call=True
    )
    def reset_iv_curve_data(n_clicks):
        if n_clicks is None:
            return dash.no_update

        # Reset the IV curve data to an empty list
        return [dict()]  # Reset to an empty list or any other default value

    @app.callback(
        Output("voltage-params", "style"),
        Output("current-params", "style"),
        Input("iv-curve-type", "value"),
    )
    def toggle_input_visibility(sweep_type):
        if sweep_type == "voltage_sweep":
            return {"display": "block"}, {"display": "none"}
        elif sweep_type == "current_sweep":
            return {"display": "none"}, {"display": "block"}
        return {"display": "none"}, {"display": "none"}


    if __name__ == "__main__":
        app.run_server(debug=True)