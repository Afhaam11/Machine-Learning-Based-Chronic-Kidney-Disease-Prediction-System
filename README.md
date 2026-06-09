# 🩺 Machine Learning-Based Chronic Kidney Disease Prediction System

## 📖 Project Overview

CKD Prediction System is a machine learning-powered web application designed to assist in the early detection of Chronic Kidney Disease (CKD) using clinical and laboratory parameters. The application leverages multiple classification algorithms combined through a Voting Ensemble Classifier to deliver reliable and accurate predictions.

Built with Streamlit, the platform provides a user-friendly interface where healthcare professionals, students, and researchers can input patient health data and instantly receive a CKD risk assessment.

The system analyzes important medical indicators such as blood pressure, blood glucose levels, serum creatinine, blood urea, hemoglobin, and several other diagnostic attributes to determine whether a patient is likely to have Chronic Kidney Disease.

---

## 🎯 Objectives

* Detect potential CKD cases using machine learning techniques.
* Improve prediction accuracy through ensemble learning.
* Provide an intuitive and interactive web-based interface.
* Demonstrate the practical application of machine learning in healthcare analytics.

---

## 🤖 Machine Learning Models Used

The prediction engine combines the strengths of multiple classification algorithms:

* Logistic Regression
* Decision Tree Classifier
* Random Forest Classifier
* XGBoost Classifier
* K-Nearest Neighbors (KNN)
* Support Vector Machine (SVM)
* Gaussian Naive Bayes

These models are integrated using a Voting Classifier Ensemble, enabling more robust and consistent predictions compared to individual models.

---

## 📊 Dataset Information

The application utilizes the Chronic Kidney Disease (CKD) dataset containing patient medical records and diagnostic measurements.

**Dataset Details**

* **File:** `kidney_disease.csv`
* **Records:** 400 patient samples
* **Features:** 24 clinical and laboratory attributes
* **Target Variable:** CKD / Not CKD

The dataset includes both numerical and categorical medical indicators commonly used in kidney disease diagnosis.

---

## 🚀 Key Features

✅ Real-time CKD risk prediction

✅ Interactive Streamlit-based user interface

✅ Ensemble machine learning architecture

✅ Automated preprocessing of categorical and numerical data

✅ Fast and accurate prediction results

✅ Easy deployment and scalability

---

## ⚙️ Installation & Setup

### Clone the Repository

```bash
git clone https://github.com/AkshayShetty7/Chronic-Kidney-Disease.git
cd Chronic-Kidney-Disease
```

### Install Required Packages

```bash
pip install -r requirements.txt
```

### Launch the Application

```bash
streamlit run app.py
```

Open the generated local URL (typically `http://localhost:8501`) in your browser.

---

## 🧠 Input Features

The model evaluates multiple clinical indicators, including:

| Feature | Description             |
| ------- | ----------------------- |
| age     | Age of patient          |
| bp      | Blood Pressure          |
| sg      | Specific Gravity        |
| al      | Albumin                 |
| su      | Sugar                   |
| bgr     | Blood Glucose Random    |
| bu      | Blood Urea              |
| sc      | Serum Creatinine        |
| sod     | Sodium                  |
| pot     | Potassium               |
| hemo    | Hemoglobin              |
| pcv     | Packed Cell Volume      |
| wc      | White Blood Cell Count  |
| rc      | Red Blood Cell Count    |
| rbc     | Red Blood Cell Status   |
| pc      | Pus Cell Status         |
| pcc     | Pus Cell Clumps         |
| ba      | Presence of Bacteria    |
| htn     | Hypertension            |
| dm      | Diabetes Mellitus       |
| cad     | Coronary Artery Disease |
| appet   | Appetite                |
| pe      | Pedal Edema             |
| ane     | Anemia                  |

---

## 📁 Project Structure

```bash
ckd-prediction/
│
├── app.py
├── kidney_disease.csv
├── ckd_voting_model.pkl
├── label_encoder.pkl
├── README.md
├── requirements.txt
└── models/
```

---

## 📈 Sample Predictions

| Patient Condition                                             | Prediction    |
| ------------------------------------------------------------- | ------------- |
| Elevated blood pressure, increased creatinine and urea levels | ⚠️ Likely CKD |
| Healthy clinical parameters and normal laboratory values      | ✅ Not CKD     |

---

## 🛠️ Technologies Used

* Python
* Streamlit
* Scikit-learn
* XGBoost
* Pandas
* NumPy
* Pickle

---

## 👨‍💻 Author

**Afhaam Ali**

Machine Learning Enthusiast | Data Science Student

Passionate about developing AI-driven healthcare solutions and applying machine learning techniques to solve real-world problems.
