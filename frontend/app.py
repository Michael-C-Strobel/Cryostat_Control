import streamlit as st
import requests
import asyncio
import websockets
import json

st.set_page_config(page_title="Cryostat Control")

# UI Elements
st.title("Cryostat Control Dashboard")
status_placeholder = st.empty()  # Placeholder for real-time updates


async def get_realtime_data():
    """Connects to WebSocket for real-time updates."""
    uri = "ws://localhost:8000/ws"  # WebSocket endpoint
    async with websockets.connect(uri) as websocket:
        while True:
            data = await websocket.recv()
            status = json.loads(data)

            # Display status in Streamlit
            status_placeholder.write(f"""
            **Temperature (Celsius):** {status["temperature"]}
            **Heater Output:** {status["heater_output"]}
            """)

            await asyncio.sleep(0.1)  # Keep listening


# Start WebSocket Listener
st.write("Listening for real-time updates...")
asyncio.run(get_realtime_data())
