# Delegación fina en quality.ps1, que es donde vive la lógica.
test:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File quality.ps1

fast:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File run-tests.ps1

lint:
	python -m ruff check .
	python -m ruff format --check .

quality: test

.PHONY: test fast lint quality
