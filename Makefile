.PHONY: install test lint app demo
install:
	pip install -r requirements-dev.txt && pip install -e .
test:
	pytest -q
lint:
	ruff check .
app:
	streamlit run app.py
demo:
	mfplan --source synthetic --target 120000 --out docs/images
