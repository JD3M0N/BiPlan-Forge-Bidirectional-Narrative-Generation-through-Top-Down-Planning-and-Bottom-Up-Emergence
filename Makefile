# Delegación fina en quality.ps1, que es donde vive la lógica.
test:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File quality.ps1

fast:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File quality.ps1 -Fast

lint:
	python -m ruff check .
	python -m ruff format --check .

quality: test

.PHONY: test fast lint quality
