import joblib # You'll use this to save/load your model
from sklearn.ensemble import RandomForestRegressor
import pandas as pd
from sklearn.linear_model import LinearRegression
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine


app = FastAPI()

# Bioequivalence Predictor

# Reference Profile (Lipitor target at 10, 20, 30, 45 mins)
LIPITOR_REF = np.array([45.2, 72.5, 89.1, 98.4])

# Define the input structure
class Recipe(BaseModel):
    mag_stearate: float
    crospovidone: float
    binder: float

def generate_virtual_lab_data():
    # Simulate 300 experiments
    np.random.seed(42)
    n_samples = 300
    
    # Inputs: Real-world ranges for Generic Lipitor
    mag_stearate = np.random.uniform(0.5, 3.0, n_samples)  # Lubricant (Slower)
    crospovidone = np.random.uniform(2.0, 10.0, n_samples) # Disintegrant (Faster)
    binder = np.random.uniform(1.0, 5.0, n_samples)       # Binder (Slightly Slower)
    
    X = np.column_stack([mag_stearate, crospovidone, binder])
    
    # Output: % Dissolved at 10, 20, 30, 45 mins
    # We create a mathematical relationship so the sliders actually WORK
    y = []
    for ms, cp, bi in X:
        # Base Lipitor-like curve + chemistry effects
        d10 = 40 + (2.0 * cp) - (6.0 * ms) - (1.0 * bi) + np.random.normal(0, 1)
        d20 = 65 + (1.5 * cp) - (4.0 * ms) - (0.8 * bi) + np.random.normal(0, 1)
        d30 = 85 + (0.8 * cp) - (2.0 * ms) - (0.5 * bi) + np.random.normal(0, 1)
        d45 = 95 + (0.3 * cp) - (1.0 * ms) - (0.2 * bi) + np.random.normal(0, 0.5)
        y.append(np.clip([d10, d20, d30, d45], 0, 100))
    
    return X, np.array(y)

X_lab, y_lab = generate_virtual_lab_data()
model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X_lab, y_lab)


@app.post("/predict_f2")
def predict_f2(recipe: Recipe):
    # 1. Predict dissolution curve
    input_data = [[recipe.mag_stearate, recipe.crospovidone, recipe.binder]]
    predicted_curve = model.predict(input_data)[0]
    
    # 2. Calculate f2 Similarity
    n = len(LIPITOR_REF)
    sum_sq_diff = np.sum((LIPITOR_REF - predicted_curve)**2)
    f2 = 50 * np.log10((1 + (1/n) * sum_sq_diff)**-0.5 * 100)
    
    return {
        "predicted_curve": predicted_curve.tolist(),
        "f2_score": round(f2, 2),
        "status": "PASS" if f2 >= 50 else "FAIL"
    }

@app.get("/feature_importance")
def get_importance():
    # Retrieve importances from the trained model
    importances = model.feature_importances_
    features = ["Magnesium Stearate", "Crospovidone", "Binder (HPC)"]
    
    # Format as a dictionary for the frontend
    data = {features[i]: round(float(importances[i]), 4) for i in range(len(features))}
    return data


# Predictive Stability (Shelf-Life)

# --- CONSTANTS ---
R = 1.986e-3  # Gas constant kcal/mol*K
SPEC_LIMIT = 0.5 # 0.5% Impurity Limit

# --- PILLAR 2: STABILITY LOGIC (Pre-calculate or train on startup) ---
def train_stability_model():
    # Synthetic ASAP Lab Results: (Temp_C, RH, Days_to_reach_0.5%)
    asap_data = [(50, 75, 14.2), (60, 40, 8.5), (70, 5, 4.1), (70, 75, 1.2), (80, 40, 0.8)]
    df = pd.DataFrame(asap_data, columns=['Temp', 'RH', 'Days'])
    
    df['k'] = SPEC_LIMIT / df['Days']
    df['ln_k'] = np.log(df['k'])
    df['inv_T'] = 1 / (df['Temp'] + 273.15)
    
    model = LinearRegression().fit(df[['inv_T', 'RH']], df['ln_k'])
    return model

stab_model = train_stability_model()

# --- SAFETY/IMPURITY LIBRARY ---
# Known Atorvastatin Degradants (Spectral Fingerprints: m/z peaks)
IMPURITY_LIBRARY = {
    "Atorvastatin_Epoxide": [155, 240, 450, 575],
    "Atorvastatin_Lactone": [112, 220, 390, 540],
    "Diketo_Impurity": [180, 260, 410, 560]
}

# --- ENDPOINTS ---

class StabilityRequest(BaseModel):
    temp: float
    rh: float

@app.post("/predict_stability")
def predict_stability(req: StabilityRequest):
    # Predict ln(k) using the trained model
    inv_T = 1 / (req.temp + 273.15)
    ln_k = stab_model.predict([[inv_T, req.rh]])[0]
    k = np.exp(ln_k)
    
    # Calculate shelf life
    shelf_life_days = SPEC_LIMIT / k
    shelf_life_months = shelf_life_days / 30.44
    
    # Extract constants for the frontend UI
    ea = -stab_model.coef_[0] * R
    b_val = stab_model.coef_[1]
    
    return {
        "shelf_life_months": round(shelf_life_months, 1),
        "ea": round(ea, 2),
        "b_factor": round(b_val, 4)
    }

class ImpurityRequest(BaseModel):
    peaks: list[float]

@app.post("/identify_impurity")
def identify_impurity(req: ImpurityRequest):
    user_peaks = sorted(req.peaks)
    best_match = None
    highest_sim = 0
    
    # Simple vector-based similarity (Placeholder for complex MS alignment)
    for name, lib_peaks in IMPURITY_LIBRARY.items():
        # Using a very basic "Peak Match Count" for this demo
        match_count = sum(1 for p in user_peaks if any(abs(p - lp) < 2 for lp in lib_peaks))
        similarity = match_count / len(lib_peaks)
        
        if similarity > highest_sim:
            highest_sim = similarity
            best_match = name
            
    if highest_sim < 0.5:
        return {"result": "Unknown Anomaly", "risk_level": "High", "similarity": highest_sim}
    
    return {"result": best_match, "risk_level": "Low (Known Degradant)", "similarity": highest_sim}