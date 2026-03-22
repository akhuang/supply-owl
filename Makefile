.PHONY: setup dev gateway

# 首次安装
setup:
	cd gateway && python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 启动 Gateway
gateway:
	cd gateway && .venv/bin/uvicorn main:app --reload --port 8321

# 启动全部 (后续补充)
dev: gateway
