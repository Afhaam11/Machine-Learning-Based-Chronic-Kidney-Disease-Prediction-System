# Legacy files

The original version of the project, kept for reference.

| File | What it is |
| --- | --- |
| `streamlit_app.py` | The first web interface (Streamlit). Superseded by the Flask app and `ckdlab/static/`. |
| `kidney_disease.ipynb` | The exploratory notebook the models were first built in. |
| `ckd_voting_model.pkl`, `label_encoder.pkl` | The pickled hard-voting ensemble and label encoder used by the Streamlit app. |
| `requirements.txt` | Dependencies for running the files above. |

To run the old interface (it loads the two pickles from its own folder):

```bash
pip install -r legacy/requirements.txt
cd legacy && streamlit run streamlit_app.py
```

The pickles were produced with specific scikit-learn and XGBoost versions and may not load on newer ones. The new app does not use them: it retrains from `data/kidney_disease.csv` and checks library versions on start-up.

One thing worth knowing about this version: the notebook trained the appetite feature with *poor = 1*, but `streamlit_app.py` sends *good = 1*, so appetite reaches the model inverted. The new code defines every encoding once, in `ckdlab/schema.py`, and has a test that guards it.
