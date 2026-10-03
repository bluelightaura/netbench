# Поднимать и гасить имеет смысл только виртуальный стенд: настоящие железки
# уже стоят, и трогать их этим makefile нечем.
#
#   make up                        L3-коммутаторы (по умолчанию)
#   make up TOPO=dc-fabric         ЦОД
#   make up TOPO=cpe-sdwan         CPE в SD-WAN
IMAGE := bench/frr-ssh:latest
TOPO  ?= l3-switches
FILE  := topologies/$(TOPO).clab.yml

image:
	docker build -t $(IMAGE) -f Dockerfile.frr-ssh .

up: image
	containerlab deploy -t $(FILE)

down:
	containerlab destroy -t $(FILE) --cleanup

status:
	containerlab inspect -t $(FILE)

# Развернуть сам проект на голой машине: Docker, containerlab, venv с
# зависимостями, образ узла и Allure. Отсюда и начинается работа на новом
# хосте — всё остальное ниже предполагает, что это уже сделано.
deploy:
	ansible-playbook -i provision/inventory.ini provision/site.yml

deploy-no-allure:
	ansible-playbook -i provision/inventory.ini provision/site.yml --skip-tags allure

# Настоящие железки: привести к известному состоянию и вернуть обратно.
# Намеренно не часть up/down — те про виртуальный стенд, а это про живое
# железо, которое никуда не поднимается и не гасится.
BENCH ?= real.local
DEVINV := provision/inventory.py

devices-baseline:
	BENCH=$(BENCH) ansible-playbook -i $(DEVINV) provision/devices-baseline.yml

devices-restore:
	BENCH=$(BENCH) ansible-playbook -i $(DEVINV) provision/devices-restore.yml

.PHONY: image up down status deploy deploy-no-allure devices-baseline devices-restore
