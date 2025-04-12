from dash import dcc, html
import dash_bootstrap_components as dbc

IV_CURVE_CARD = dbc.Card(
    [
        # State to hold the connection status
        dcc.Store(id="sourcemeter-connection-status", storage_type="session",),
        
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
        dbc.Button("Take IV Curve Measurement", id="manual-iv-curve-btn", disabled=True),
        # Card Header and Body for IV Curves
        dbc.CardHeader("IV Curves"),
        dbc.CardBody([
                    dcc.Graph(id="iv-curve-plot", config={"displayModeBar": False}),
                    # Download Link for Data (iv-curve-download-button)
                    dbc.Button("Download IV Curve Data", id="iv-curve-download-button", color="primary"),
                    dcc.Download(id="iv-curve-download"),  # Download component to trigger the download
                    # Button for clearing the data
                    dbc.Button("Clear Data", id="iv-curve-clear-data", color="danger"),
                    dbc.Row(
                        [
                            # Lower Voltage Input
                            dbc.Col(
                                [
                                    dbc.Label("Lower Voltage"),
                                    dbc.Input(id="sourcemeter-voltage-lower", type="number", placeholder="Lower voltage", debounce=True, value=-0.05),
                                ], 
                                width=4
                            ),
                            # Upper Voltage Input
                            dbc.Col(
                                [
                                    dbc.Label("Upper Voltage"),
                                    dbc.Input(id="sourcemeter-voltage-upper", type="number", placeholder="Upper voltage", debounce=True, value=0.05),
                                ], 
                                width=4
                            ),
                            # Voltage Step Input
                            dbc.Col(
                                [
                                    dbc.Label("Voltage Step"),
                                    dbc.Input(id="sourcemeter-voltage-step", type="number", placeholder="Voltage step", debounce=True, value=0.01),
                                ], 
                                width=4
                            )
                        ]
                    ),
                    dbc.Row(
                        [
                            # Source Meter Compliance Current Input
                            dbc.Col(
                                [
                                    dbc.Label("Compliance Current (A)"),
                                    dbc.Input(id="sourcemeter-compliance-current", type="number", placeholder="Compliance current", debounce=True, value=0.1),
                                ], 
                                width=4
                            ),
                            # Source Meter Voltage Range Input
                            dbc.Col(
                                [
                                    dbc.Label("Voltage Range (V)"),
                                    dbc.Input(id="sourcemeter-voltage-range", type="number", placeholder="Voltage range", debounce=True, value=5),
                                ], 
                                width=4
                            ),
                        ]
                    )
                ])
    ]
)
