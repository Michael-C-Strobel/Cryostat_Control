from dash import Input, Output
import plotly.graph_objs as go
import json
from dash import Dash, dcc, html
from dash_extensions import WebSocket

def register_callbacks(app):
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

    # WebSocket message handler for temperature stability notifications
    @app.callback(
        Output("iv-curve-data", "data"),
        Input("ws", "message"),
        State("voltage-lower", "value"),
        State("voltage-upper", "value"),
        State("voltage-step", "value"),
        prevent_initial_call=True
    )
    def handle_stability_notification(iv_curve_data, message):
        """Handle temperature stability notifications from the backend."""
        iv_curve_data = iv_curve_data
        if iv_curve_data is None:
            iv_curve_data = {}

        if not message:
            return iv_curve_data

        data = json.loads(message["data"])
        stable_temp = data.get("stable_temperature")
        if stable_temp is not None:
            try:
                lb = float(data["voltage_lower_bound"])
                ub = float(data["voltage_upper_bound"])
                step = float(data["voltage_step"])
            except ValueError:
                raise ValueError("Invalid voltage range or step value.")
            except KeyError:
                raise KeyError("Missing voltage range or step value.")

            voltages = list(range(lb, ub, step))

            # Perform IV curve measurement via ws iv-curve-data-ws
            socket = WebSocket(id="iv-curve-data-ws", url="ws://localhost:8001/measure_iv_curve")
            content = socket.send_text(json.dumps({"voltages": voltages}))
            new_mesaurement = json.loads(content)

        return iv_curve_data

    # Register IV Curve Callbacks
    register_iv_curve_callbacks(app)