from dash import dcc, html
import dash_bootstrap_components as dbc

IV_CURVE_CARD = dbc.Card([
    dbc.Input(id="adapter-input", placeholder="Enter adapter identifier", type="text"),
    dbc.Button("Connect", id="connect-button", color="primary", className="mr-2"),
    dbc.Button("Check Connections", id="sourcemeter_check_connections", color="secondary", className="mr-2"),
    dbc.Alert(id="sourcemeter-state", color="info", children="Sourcemeter state: Disconnected"),
    dbc.CardHeader("IV Curves"),
    dbc.CardBody([
        dcc.Graph(id="iv-curve-plot", config={"displayModeBar": False})
    ])
])