import streamlit as st
import pandas as pd
import joblib

# -----------------------------
# Load trained model and encoder
# -----------------------------
model = joblib.load("ckd_voting_model.pkl")
le = joblib.load("label_encoder.pkl")  # used for output label decoding

st.title("🩺 Chronic Kidney Disease (CKD) Prediction App")
st.write("Enter patient medical parameters below to predict the risk of CKD.")

# -----------------------------
# Numeric Inputs
# -----------------------------
age = st.number_input("Age (years)", 0, 120, 30)
bp = st.number_input("Blood Pressure (mm Hg)", 0, 200, 80)
sg = st.number_input("Specific Gravity", 1.0, 2.0, 1.02)
al = st.number_input("Albumin (0–5)", 0, 5, 1)
su = st.number_input("Sugar (0–5)", 0, 5, 0)
bgr = st.number_input("Blood Glucose Random (mg/dL)", 0, 500, 120)
bu = st.number_input("Blood Urea (mg/dL)", 0, 300, 40)
sc = st.number_input("Serum Creatinine (mg/dL)", 0.0, 20.0, 1.0)
sod = st.number_input("Sodium (mEq/L)", 0.0, 200.0, 140.0)
pot = st.number_input("Potassium (mEq/L)", 0.0, 20.0, 4.5)
hemo = st.number_input("Hemoglobin (g/dL)", 0.0, 30.0, 15.0)
pcv = st.number_input("Packed Cell Volume (%)", 0, 60, 40)
wc = st.number_input("White Blood Cell Count (/cmm)", 0, 20000, 8000)
rc = st.number_input("Red Blood Cell Count (million/cmm)", 0.0, 10.0, 5.0)

# -----------------------------
# Categorical Inputs
# -----------------------------
rbc = st.selectbox("Red Blood Cell (RBC)", ["normal", "abnormal"])
pc = st.selectbox("Pus Cell (PC)", ["normal", "abnormal"])
pcc = st.selectbox("Pus Cell Clumps (PCC)", ["present", "absent"])
ba = st.selectbox("Bacteria (BA)", ["present", "absent"])
htn = st.selectbox("Hypertension (HTN)", ["yes", "no"])
dm = st.selectbox("Diabetes Mellitus (DM)", ["yes", "no"])
cad = st.selectbox("Coronary Artery Disease (CAD)", ["yes", "no"])
appet = st.selectbox("Appetite", ["good", "poor"])
pe = st.selectbox("Pedal Edema (PE)", ["yes", "no"])
ane = st.selectbox("Anemia (ANE)", ["yes", "no"])

# -----------------------------
# Create input DataFrame
# -----------------------------
input_data = pd.DataFrame({
    'age':[age], 'bp':[bp], 'sg':[sg], 'al':[al], 'su':[su], 'bgr':[bgr], 'bu':[bu],
    'sc':[sc], 'sod':[sod], 'pot':[pot], 'hemo':[hemo], 'pcv':[pcv], 'wc':[wc], 'rc':[rc],
    'rbc':[rbc], 'pc':[pc], 'pcc':[pcc], 'ba':[ba], 'htn':[htn], 'dm':[dm], 'cad':[cad],
    'appet':[appet], 'pe':[pe], 'ane':[ane]
})

# -----------------------------
# Encode categorical variables
# -----------------------------
mapping = {
    'rbc': {'normal': 1, 'abnormal': 0},
    'pc': {'normal': 1, 'abnormal': 0},
    'pcc': {'present': 1, 'absent': 0},
    'ba': {'present': 1, 'absent': 0},
    'htn': {'yes': 1, 'no': 0},
    'dm': {'yes': 1, 'no': 0},
    'cad': {'yes': 1, 'no': 0},
    'appet': {'good': 1, 'poor': 0},
    'pe': {'yes': 1, 'no': 0},
    'ane': {'yes': 1, 'no': 0}
}

for col, m in mapping.items():
    input_data[col] = input_data[col].map(m)

# -----------------------------
# Predict
# -----------------------------
if st.button("Predict CKD"):
    try:
        pred_num = model.predict(input_data)[0]
        pred_label = le.inverse_transform([pred_num])[0]
        st.success(f"🩸 Prediction: **{pred_label.upper()}**")
        if pred_label == "ckd":
            st.warning("⚠️ Patient is likely to have Chronic Kidney Disease.")
        else:
            st.info("✅ Patient is unlikely to have CKD.")
    except Exception as e:
        st.error(f"Error during prediction: {e}")
