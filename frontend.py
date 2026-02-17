import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt

# Configuration
st.set_page_config(page_title="ANDA Launch Accelerator", layout="wide")
BACKEND_URL = "http://localhost:8000"

st.title("🚀 ANDA Launch Accelerator: Digital Triage Suite")
st.markdown("---")

# Create Tabs for the Three Pillars
tab1, tab2, tab3 = st.tabs(["💊 Dissolution (f2)", "⏳ Stability (ASAP)", "🛡️ Safety (Impurity)"])

# --- TAB 1: DISSOLUTION (f2 MATCHING) ---
with tab1:
    st.header("Bioequivalence: f2 Similarity Predictor")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Formulation Recipe")
        ms = st.slider("Magnesium Stearate (%)", 0.5, 3.0, 1.2)
        cp = st.slider("Crospovidone (%)", 2.0, 10.0, 5.0)
        bi = st.slider("Binder (%)", 1.0, 5.0, 3.0)
        
        if st.button("Predict f2 Score"):
            payload = {"mag_stearate": ms, "crospovidone": cp, "binder": bi}
            res = requests.post(f"{BACKEND_URL}/predict_f2", json=payload).json()
            
            st.metric("f2 Score", res['f2_score'])
            if res['status'] == "PASS":
                st.success("✅ BIOEQUIVALENT")
            else:
                st.error("❌ NON-EQUIVALENT")

    with col2:
        if 'res' in locals():
            st.subheader("Predicted Dissolution Profile")
            fig, ax = plt.subplots()
            time_pts = [10, 20, 30, 45]
            ref_vals = [45.2, 72.5, 89.1, 98.4] # Reference (Lipitor)
            ax.plot(time_pts, ref_vals, 'o-', label="Reference (Lipitor)")
            ax.plot(time_pts, res['predicted_curve'], 's--', label="Generic Prediction")
            ax.set_ylim(0, 105); ax.legend()
            st.pyplot(fig)


    st.markdown("---")
    st.subheader("Sensitivity Analysis: Which Excipient Matters Most?")

    if st.button("Analyze Sensitivity"):
        imp_res = requests.get(f"{BACKEND_URL}/feature_importance").json()
        
        # Convert to DataFrame for easy plotting
        imp_df = pd.DataFrame(list(imp_res.items()), columns=['Excipient', 'Importance'])
        imp_df = imp_df.sort_values(by='Importance', ascending=True)
        
        fig_imp, ax_imp = plt.subplots()
        ax_imp.barh(imp_df['Excipient'], imp_df['Importance'], color='teal')
        ax_imp.set_xlabel("Relative Impact on Dissolution")
        st.pyplot(fig_imp)
        
        st.info("💡 Insight: Focus on adjusting the excipient with the highest impact to match the RLD profile faster.")

# --- TAB 2: STABILITY (ASAP PREDICTOR) ---
with tab2:
    st.header("Stability: ASAP Shelf-Life Predictor")
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.subheader("Storage Conditions")
        target_t = st.number_input("Target Storage Temp (°C)", value=25)
        target_rh = st.slider("Target Humidity (%RH)", 30, 80, 60)
        
        if st.button("Calculate Shelf-Life"):
            payload = {"temp": target_t, "rh": target_rh}
            stab_res = requests.post(f"{BACKEND_URL}/predict_stability", json=payload).json()
            
            st.metric("Predicted Shelf-Life", f"{stab_res['shelf_life_months']} Months")
            st.info(f"Activation Energy (Ea): {stab_res['ea']} kcal/mol")
            st.info(f"Humidity Factor (B): {stab_res['b_factor']}")

    with col_b:
        st.subheader("Stability Risk Heatmap")
        # Logic to generate heatmap data for the UI
        temps = np.linspace(20, 40, 10)
        rhs = np.linspace(30, 75, 10)
        z = []
        # Calling backend logic here via helper or direct calculation for speed
        for t in temps:
            row = []
            for h in rhs:
                # We reuse the stability formula logic locally for the heatmap visualization
                # This mimics calling the backend for many points
                payload = {"temp": t, "rh": h}
                val = requests.post(f"{BACKEND_URL}/predict_stability", json=payload).json()['shelf_life_months']
                row.append(val)
            z.append(row)
        
        fig_heat = px.imshow(z, x=rhs, y=temps, color_continuous_scale='RdYlGn',
                             labels=dict(x="Humidity %", y="Temp °C", color="Months"))
        st.plotly_chart(fig_heat)

# --- TAB 3: SAFETY (IMPURITY FINGERPRINT) ---
with tab3:
    st.header("Safety: Automated Impurity Identification")
    st.write("Enter the highest m/z peaks found in your lab LC-MS result:")
    
    p1 = st.number_input("Peak 1 (m/z)", value=0.0)
    p2 = st.number_input("Peak 2 (m/z)", value=0.0)
    p3 = st.number_input("Peak 3 (m/z)", value=0.0)
    
    if st.button("Identify Impurity"):
        payload = {"peaks": [p1, p2, p3]}
        safe_res = requests.post(f"{BACKEND_URL}/identify_impurity", json=payload).json()
        
        st.write(f"**Result:** {safe_res['result']}")
        st.write(f"**Risk Level:** {safe_res['risk_level']}")
        st.progress(safe_res['similarity'])