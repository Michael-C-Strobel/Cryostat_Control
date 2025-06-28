from dash import dcc, html
import dash_bootstrap_components as dbc

VOLTAGE_SWEEP_INPUT = [
    dbc.Row([
        dbc.Col([
            dbc.Label("Lower Voltage"),
            dbc.Input(id="sourcemeter-voltage-lower", type="number", debounce=True, value=-0.05),
        ], width=4),
        dbc.Col([
            dbc.Label("Upper Voltage"),
            dbc.Input(id="sourcemeter-voltage-upper", type="number", debounce=True, value=0.05),
        ], width=4),
        dbc.Col([
            dbc.Label("Voltage Step"),
            dbc.Input(id="sourcemeter-voltage-step", type="number", debounce=True, value=0.01),
        ], width=4)
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Label("Compliance Current (A)"),
            dbc.Input(id="sourcemeter-compliance-current", type="number", debounce=True, value=0.1),
        ], width=4),
        dbc.Col([
            dbc.Label("Voltage Range (V)"),
            dbc.Input(id="sourcemeter-voltage-range", type="number", debounce=True, value=5),
        ], width=4)
    ])
]

CURRENT_SWEEP_INPUT = [
    dbc.Row([
        dbc.Col([
            dbc.Label("Lower Current"),
            dbc.Input(id="sourcemeter-current-lower", type="number", debounce=True, value=-0.001),
        ], width=4),
        dbc.Col([
            dbc.Label("Upper Current"),
            dbc.Input(id="sourcemeter-current-upper", type="number", debounce=True, value=0.001),
        ], width=4),
        dbc.Col([
            dbc.Label("Current Step"),
            dbc.Input(id="sourcemeter-current-step", type="number", debounce=True, value=0.0001),
        ], width=4)
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Label("Compliance Voltage (V)"),
            dbc.Input(id="sourcemeter-compliance-voltage", type="number", debounce=True, value=5),
        ], width=4),
        dbc.Col([
            dbc.Label("Current Range (A)"),
            dbc.Input(id="sourcemeter-current-range", type="number", debounce=True, value=0.01),
        ], width=4)
    ])
]

IV_CURVE_CARD = dbc.Card(
    [
        dcc.Store(id="sourcemeter-connection-status", storage_type="session"),

        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        id="sourcemeter-adapter-input",
                        placeholder="Select an adapter",
                        options=[],
                        multi=False
                    ),
                    width=8
                ),
                dbc.Col(
                    dbc.Button("Check Connections", id="sourcemeter-check-connections", color="secondary"),
                    width=4
                )
            ]
        ),
        dbc.Button("Connect", id="sourcemeter-connect-button", color="primary"),
        dbc.Alert(id="sourcemeter-state", color="info", children="Sourcemeter state: Disconnected"),
        dbc.Button("Take IV Curve Measurement", id="manual-iv-curve-btn", disabled=True),

        dbc.CardHeader("IV Curves"),
        dbc.CardBody(
            [
                dcc.Graph(id="iv-curve-plot", config={"displayModeBar": False}),
                dbc.Button("Download IV Curve Data", id="iv-curve-download-button", color="primary"),
                dcc.Download(id="iv-curve-download"),
                dbc.Button("Clear Data", id="iv-curve-clear-data", color="danger"),

                dcc.RadioItems(
                    id="iv-curve-type",
                    options=[
                        {"label": "Voltage Sweep", "value": "voltage_sweep"},
                        {"label": "Current Sweep", "value": "current_sweep"}
                    ],
                    value="voltage_sweep",
                    labelStyle={"display": "block"},
                    inline=False
                ),

                html.Div(id="voltage-params", children=VOLTAGE_SWEEP_INPUT, style={"display": "block"}),
                html.Div(id="current-params", children=CURRENT_SWEEP_INPUT, style={"display": "none"}),

            ]
        )
    ]
)