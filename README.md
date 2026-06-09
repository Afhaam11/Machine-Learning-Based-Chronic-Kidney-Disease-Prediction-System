# 🩺 Chronic Kidney Disease (CKD) Prediction App

## 📘 Overview
This project is a machine learning web app built with Streamlit that predicts the likelihood of Chronic Kidney Disease (CKD) based on medical parameters such as blood pressure, blood urea, serum creatinine, hemoglobin, and other biochemical indicators.

The app combines several machine learning models — Logistic Regression, Decision Tree, Random Forest, XGBoost, KNN, SVM, and Naive Bayes — into a Voting Classifier Ensemble, providing a robust and accurate prediction system.

Users can input patient details via an interactive Streamlit form, and the app outputs whether the patient is likely to have CKD or not.

### 📊 Dataset

This project uses the Chronic Kidney Disease (CKD) dataset.

* **File name:** `kidney_disease.csv`
* **Location:** Same folder as `app.py`
* **Description:** Contains 400 patient records with 25 clinical features and a target variable (`ckd` or `notckd`) used for prediction.
* **Example path in project:**
    ```
    ./kidney_disease.csv
    ```

---

### ⚙️ Installation and Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/AkshayShetty7/Chronic-Kidney-Disease.git
    cd Chronic-Kidney-Disease

    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Streamlit App**
    ```bash
    streamlit run app.py
    ```
    Then open the displayed local URL in your browser (usually `http://localhost:8501`).

---

### 🧠 Features Used

| Abbreviation | Description                      |
| :----------- | :------------------------------- |
| **age** | Age (years)                      |
| **bp** | Blood Pressure (mm Hg)           |
| **sg** | Specific Gravity                 |
| **al** | Albumin                          |
| **su** | Sugar                            |
| **bgr** | Blood Glucose Random (mg/dL)     |
| **bu** | Blood Urea (mg/dL)               |
| **sc** | Serum Creatinine (mg/dL)         |
| **sod** | Sodium (mEq/L)                   |
| **pot** | Potassium (mEq/L)                |
| **hemo** | Hemoglobin (g/dL)                |
| **pcv** | Packed Cell Volume (%)           |
| **wc** | White Blood Cell Count (/cmm)    |
| **rc** | Red Blood Cell Count (million/cmm) |
| **rbc** | Red Blood Cells (normal/abnormal)|
| **pc** | Pus Cells (normal/abnormal)      |
| **pcc** | Pus Cell Clumps (present/absent) |
| **ba** | Bacteria (present/absent)        |
| **htn** | Hypertension (yes/no)            |
| **dm** | Diabetes Mellitus (yes/no)       |
| **cad** | Coronary Artery Disease (yes/no) |
| **appet** | Appetite (good/poor)             |
| **pe** | Pedal Edema (yes/no)             |
| **ane** | Anemia (yes/no)                  |

---

### 📁 Project Structure

```bash
ckd-prediction/
│
├── app.py                    # Streamlit web app
├── kidney_disease.csv        # Local dataset
├── ckd_voting_model.pkl      # Trained ensemble model
├── label_encoder.pkl         # Label encoder for target variable
├── README.md                 # Project documentation
├── requirements.txt          # Dependencies
└── models/                   # Optional folder for storing models


```

---

### 🧾 Example Predictions

| Case                                        | Result      |
| :------------------------------------------ | :---------- |
| Elderly patient, high BP, high urea/creatinine | ⚠️ Likely CKD |
| Young healthy patient, normal vitals        | ✅ Not CKD    |

---

### 👨‍⚕️ Author

**Akshay Shetty**

*Machine Learning Enthusiast | Data Science Student*
