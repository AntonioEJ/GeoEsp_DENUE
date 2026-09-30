.PHONY: setup lint format test download-denue process-denue clean

setup:
	uv sync

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

test:
	uv run pytest tests/ -v

download-denue:
	uv run python src/ingesta/descargar_denue.py

process-denue:
	uv run python src/preprocesamiento/limpiar_denue.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +
