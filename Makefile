.PHONY: dev test install lint

dev:
	uvicorn backend.app.main:app --reload --port 8000

test:
	pytest backend/tests/ -v

install:
	pip install -r requirements.txt
