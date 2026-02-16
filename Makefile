# --- Variables comunes ---
IMAGE = alma-whatsapp-message-orchestrator
TAG   = latest
PORT  = 8080
VENV  = .venv

# --- Targets para LOCAL ---
.PHONY: venv install run-local clean

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

install: venv
	$(VENV)/bin/pip install -r requirements.txt

# Usa Opción A (una línea) o B (.ONESHELL). Aquí dejo la A:
run-local:
	( set -a && . .env && exec $(VENV)/bin/python -m uvicorn src.app:app --host 0.0.0.0 --port $(PORT) --reload )

clean:
	rm -rf $(VENV)

# --- Targets para DOCKER ---
.PHONY: build run run-d stop logs up down shell inspect-env ps rebuild rm-image

build:
	docker build -t $(IMAGE):$(TAG) .

# Levanta el contenedor usando variables desde .env
run:
	docker run --name $(IMAGE) --rm \
		--env-file .env \
		-p $$(grep PORT .env | cut -d '=' -f2):8080 \
		$(IMAGE):$(TAG)

# Modo detached (en segundo plano)
run-d:
	docker run -d --name $(IMAGE) \
		--env-file .env \
		-p $$(grep PORT .env | cut -d '=' -f2):8080 \
		$(IMAGE):$(TAG)

stop:
	-@docker stop $(IMAGE) 2>/dev/null || true

logs:
	docker logs -f $(IMAGE)

# Atajos
up: build run
down: stop
rebuild:
	docker build --no-cache -t $(IMAGE):$(TAG) .

# Abre una shell dentro del contenedor en ejecución
shell:
	@docker exec -it $(IMAGE) /bin/sh 2>/dev/null || docker exec -it $(IMAGE) /bin/bash

# Ver variables de entorno dentro del contenedor
inspect-env:
	docker exec -it $(IMAGE) env | sort

# Listar contenedores (útil para verificar si está corriendo)
ps:
	docker ps --filter "name=$(IMAGE)"

# Eliminar la imagen (si necesitas limpiar)
rm-image:
	-@docker rmi $(IMAGE):$(TAG) 2>/dev/null || true