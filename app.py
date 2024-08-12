import streamlit as st
from lakeshore import Model335

# Write the page label
st.set_page_config(
    page_title="Cryostat Control",
)


def initalize_connection(heater_resistance, max_current):
    cryo = Model335(57600)

    display_setting  = cryo.HeaterOutputDisplay.POWER
    cryo.set_heater_setup_one(heater_resistance, max_current, display_setting)
    return cryo

if not st.session_state.get("num_points"):
    st.session_state.num_points = 1

if not st.session_state.get("setpoints"):
    st.session_state.setpoints = [0.0 for _ in range(st.session_state.num_points)]

with st.sidebar:
    st.write("Settings")
    st.slider("Number of temperature points", 1, 100, key="num_points")

    # Update session_state_setpoints
    st.session_state.setpoints = st.session_state.setpoints[:st.session_state.num_points]
    st.session_state.setpoints += [0.0 for _ in range(st.session_state.num_points - len(st.session_state.setpoints))]

    with st.form(key="temperature_points"):
        for i in range(st.session_state.num_points):
            st.session_state.setpoints[i] = st.number_input(f"Temperature {i+1}", key=f"setpoints.{i}")

        st.form_submit_button("Update Setpoints")
    

# Plot the set points
st.line_chart(st.session_state.setpoints,
              x_label="Temperature Point",
              y_label="Temperature (K)",)

