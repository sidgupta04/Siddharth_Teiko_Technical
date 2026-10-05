PYTHON ?= python

.PHONY: setup pipeline dashboard

setup:
	"$(PYTHON)" -m pip install -r requirements.txt

pipeline:
	"$(PYTHON)" load_data.py
	"$(PYTHON)" run_analysis.py

dashboard:
	"$(PYTHON)" -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
