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
    uri = "ws://backend:8000/ws"  # Use the service name from docker-compose
    async with websockets.connect(uri) as websocket:
        while True:
            data = await websocket.recv()
            status = json.loads(data)

            # Display all data
            st.write("Received data:", status)

            # Display status in Streamlit
            status_placeholder.write(f"""
            **Temperature (Celsius):** {status.get("temperature", "Unknown")}
            **Heater Output:** {status.get("heater_output", "Unknown")}
            """)

            await asyncio.sleep(0.01)  # Keep listening


# Start WebSocket Listener
st.write("Listening for real-time updates...")
asyncio.run(get_realtime_data())
