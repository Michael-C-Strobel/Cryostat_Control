from dash import dcc, html
import dash_bootstrap_components as dbc

IV_CURVE_CARD = dbc.Card(
    [
        # State to hold the connection status
        dcc.Store(id="sourcemeter-connection-status", storage_type="session"),
        
        # Dropdown and Button for checking connections
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        id="sourcemeter-adapter-input",  # Prefixed ID
                        placeholder="Select an adapter",
                        options=[],  # The options will be populated dynamically
                        multi=False  # You can change this to True if you want multi-select
                    ),
                    width=8
                ),
                dbc.Col(
                    dbc.Button("Check Connections", id="sourcemeter-check-connections", color="secondary", className="mr-2"),  # Prefixed ID
                    width=4
                )
            ]
        ),
        
        # Button for initializing the connection
        dbc.Button("Connect", id="sourcemeter-connect-button", color="primary", className="mr-2"),  # Prefixed ID
        
        # Alert to display connection status
        dbc.Alert(id="sourcemeter-state", color="info", children="Sourcemeter state: Disconnected"),  # Prefixed ID
        dbc.Button("Take IV Curve Measurement", id="manual-iv-curve-btn"),
        # Card Header and Body for IV Curves
        dbc.CardHeader("IV Curves"),
        dbc.CardBody([
            dcc.Graph(id="iv-curve-plot", config={"displayModeBar": False}),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Lower Voltage"),  # Label for the lower voltage input
                            dcc.Input(id="sourcemeter-voltage-lower", type="number", placeholder="Lower voltage", debounce=True, value=-0.005),
                        ], 
                        width=4
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Upper Voltage"),  # Label for the upper voltage input
                            dcc.Input(id="sourcemeter-voltage-upper", type="number", placeholder="Upper voltage", debounce=True, value=0.005),
                        ], 
                        width=4
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Voltage Step"),  # Label for the voltage step input
                            dcc.Input(id="sourcemeter-voltage-step", type="number", placeholder="Voltage step", debounce=True, value=0.001),
                        ], 
                        width=4
                    )
                ]
            )
        ])
    ]
)
