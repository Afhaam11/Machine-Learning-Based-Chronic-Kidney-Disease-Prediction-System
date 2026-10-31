import joblib
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="CKD Risk Assessment",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

    :root { --ink: #172b3a; --muted: #627586; --teal: #087e82; --line: #dce8e9; }
    .stApp { background: #f4f8f8; color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(244,248,248,.92); }
    [data-testid="stAppViewContainer"] .main .block-container {
        max-width: 1120px; padding: 2.4rem 2rem 4rem; font-family: 'DM Sans', sans-serif;
    }}
    h1, h2, h3 { font-family: 'Manrope', sans-serif !important; color: var(--ink); }
    .hero { background: linear-gradient(120deg,#0b5968 0%,#087e82 62%,#19a39a 100%);
        border-radius: 22px; padding: 2.2rem 2.4rem; color: white; margin-bottom: 1.3rem;
        box-shadow: 0 16px 34px rgba(8,91,103,.16); }
    .hero-kicker { text-transform: uppercase; letter-spacing: .15em; font-size: .75rem;
        font-weight: 700; opacity: .78; margin-bottom: .7rem; }
    .hero h1 { color: white !important; font-size: clamp(2rem,4vw,3rem); line-height: 1.12;
        margin: 0 0 .65rem; }
    .hero p { color: rgba(255,255,255,.88); font-size: 1rem; margin: 0; max-width: 720px; }
    .notice { border: 1px solid #d9e8e8; background: #fff; color: #516777; border-radius: 12px;
        padding: .85rem 1rem; font-size: .88rem; margin: 0 0 1.35rem; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: white; border: 1px solid var(--line);
        border-radius: 16px; padding: 1.15rem 1.35rem; box-shadow: 0 5px 18px rgba(28,59,69,.035); }
    [data-testid="stWidgetLabel"] p { color: #344d5d; font-weight: 600; font-size: .9rem; }
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { border-radius: 9px; }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        width: 100%; border: 0; border-radius: 10px; min-height: 3rem; color: white;
        background: #087e82; font-weight: 700; transition: background .15s ease, transform .15s ease;
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        background: #06696d; color: white; transform: translateY(-1px);
    }
    .result-heading { font-family: 'Manrope',sans-serif; font-size: 1.35rem; font-weight: 800;
        margin: 1.5rem 0 .8rem; color: var(--ink); }
    .footer { color: #738594; font-size: .8rem; text-align: center; margin-top: 2rem; }
    @media (max-width: 640px) {
        [data-testid="stAppViewContainer"] .main .block-container { padding: 1rem .8rem 2.5rem; }
        .hero { padding: 1.5rem; border-radius: 16px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero">
      <div class="hero-kicker">Clinical decision support demo</div>
      <h1>Kidney health risk assessment</h1>
      <p>Enter the available patient measurements to generate a model prediction. Complete the fields using the units shown.</p>
    </section>
    <div class="notice">For educational and research use only. This model does not provide a diagnosis or replace assessment by a qualified healthcare professional.</div>
    """,
    unsafe_allow_html=True,
)

theme_choice = st.radio(
    "Appearance",
    ["Light", "Dark"],
    horizontal=True,
    label_visibility="collapsed",
    key="appearance_theme",
)
theme = "dark" if theme_choice == "Dark" else "light"
st.markdown(
    f"""
    <style>
    :root {{
      color-scheme: {theme};
      --page: { '#101a22' if theme == 'dark' else '#f4f8f8' };
      --surface: { '#192832' if theme == 'dark' else '#ffffff' };
      --ink: { '#edf5f7' if theme == 'dark' else '#172b3a' };
      --muted: { '#a8bbc5' if theme == 'dark' else '#627586' };
      --line: { '#30444e' if theme == 'dark' else '#dce8e9' };
      --label: { '#d5e2e7' if theme == 'dark' else '#344d5d' };
      --control: { '#21343f' if theme == 'dark' else '#ffffff' };
    }}
    .stApp, [data-testid="stAppViewContainer"] {{ background: var(--page) !important; color: var(--ink) !important; }}
    [data-testid="stHeader"] {{ background: var(--page) !important; }}
    h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] {{ color: var(--ink); }}
    .hero h1, .hero p {{ color: white !important; }}
    .notice {{ background: var(--surface); border-color: var(--line); color: var(--muted); }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ background: var(--surface); border-color: var(--line); }}
    [data-testid="stWidgetLabel"] p {{ color: var(--label) !important; }}
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
      background: var(--control); border-color: var(--line);
    }}
    div[data-baseweb="select"] input, div[data-baseweb="input"] input {{ color: var(--ink); }}
    [data-testid="stNumberInput"] button {{ color: var(--ink); }}
    .result-heading {{ color: var(--ink); }}
    .footer {{ color: var(--muted); }}
    [data-testid="stRadio"] label {{ color: var(--ink) !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Load the trained model and label encoder.
model = joblib.load("ckd_voting_model.pkl")
le = joblib.load("label_encoder.pkl")

with st.form("patient_input"):
    with st.container(border=True):
        st.subheader("Patient measurements")
        st.caption("Core clinical and laboratory values")
        c1, c2, c3, c4 = st.columns(4)
        age = c1.number_input("Age (years)", 0, 120, 30)
        bp = c2.number_input("Blood pressure (mm Hg)", 0, 200, 80)
        sg = c3.number_input("Specific gravity", 1.0, 2.0, 1.02, format="%.3f")
        al = c4.number_input("Albumin (0–5)", 0, 5, 1)

        c1, c2, c3, c4 = st.columns(4)
        su = c1.number_input("Sugar (0–5)", 0, 5, 0)
        bgr = c2.number_input("Random glucose (mg/dL)", 0, 500, 120)
        bu = c3.number_input("Blood urea (mg/dL)", 0, 300, 40)
        sc = c4.number_input("Serum creatinine (mg/dL)", 0.0, 20.0, 1.0, format="%.2f")

        c1, c2, c3, c4 = st.columns(4)
        sod = c1.number_input("Sodium (mEq/L)", 0.0, 200.0, 140.0, format="%.1f")
        pot = c2.number_input("Potassium (mEq/L)", 0.0, 20.0, 4.5, format="%.1f")
        hemo = c3.number_input("Hemoglobin (g/dL)", 0.0, 30.0, 15.0, format="%.1f")
        pcv = c4.number_input("Packed cell volume (%)", 0, 60, 40)

        c1, c2 = st.columns(2)
        wc = c1.number_input("White blood cell count (/cmm)", 0, 20000, 8000)
        rc = c2.number_input("Red blood cell count (million/cmm)", 0.0, 10.0, 5.0, format="%.2f")

    with st.container(border=True):
        st.subheader("Clinical indicators")
        st.caption("Choose the option that best matches the patient's record")
        c1, c2, c3 = st.columns(3)
        rbc = c1.selectbox("Red blood cells", ["normal", "abnormal"])
        pc = c2.selectbox("Pus cells", ["normal", "abnormal"])
        pcc = c3.selectbox("Pus cell clumps", ["present", "absent"])

        c1, c2, c3 = st.columns(3)
        ba = c1.selectbox("Bacteria", ["present", "absent"])
        htn = c2.selectbox("Hypertension", ["yes", "no"])
        dm = c3.selectbox("Diabetes mellitus", ["yes", "no"])

        c1, c2, c3, c4 = st.columns(4)
        cad = c1.selectbox("Coronary artery disease", ["yes", "no"])
        appet = c2.selectbox("Appetite", ["good", "poor"])
        pe = c3.selectbox("Pedal edema", ["yes", "no"])
        ane = c4.selectbox("Anemia", ["yes", "no"])

    submitted = st.form_submit_button("Assess risk")

if submitted:
    input_data = pd.DataFrame(
        {
            "age": [age], "bp": [bp], "sg": [sg], "al": [al], "su": [su],
            "bgr": [bgr], "bu": [bu], "sc": [sc], "sod": [sod], "pot": [pot],
            "hemo": [hemo], "pcv": [pcv], "wc": [wc], "rc": [rc], "rbc": [rbc],
            "pc": [pc], "pcc": [pcc], "ba": [ba], "htn": [htn], "dm": [dm],
            "cad": [cad], "appet": [appet], "pe": [pe], "ane": [ane],
        }
    )

    mapping = {
        "rbc": {"normal": 1, "abnormal": 0},
        "pc": {"normal": 1, "abnormal": 0},
        "pcc": {"present": 1, "absent": 0},
        "ba": {"present": 1, "absent": 0},
        "htn": {"yes": 1, "no": 0},
        "dm": {"yes": 1, "no": 0},
        "cad": {"yes": 1, "no": 0},
        "appet": {"good": 1, "poor": 0},
        "pe": {"yes": 1, "no": 0},
        "ane": {"yes": 1, "no": 0},
    }
    for col, values in mapping.items():
        input_data[col] = input_data[col].map(values)

    try:
        pred_num = model.predict(input_data)[0]
        pred_label = le.inverse_transform([pred_num])[0]
        st.markdown('<div class="result-heading">Assessment result</div>', unsafe_allow_html=True)
        if str(pred_label).lower() == "ckd":
            st.error("The model prediction indicates CKD.")
        else:
            st.success("The model prediction indicates not CKD.")
        st.caption("This is a machine learning output and should be interpreted by a qualified clinician in context.")
    except Exception as exc:
        st.error(f"Prediction could not be completed: {exc}")

st.markdown('<div class="footer">CKD Risk Assessment · Machine learning demonstration</div>', unsafe_allow_html=True)
