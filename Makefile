SERVICE = gcp-networking
HOST := us-docker.pkg.dev
REPO := cloudbuild
PROJECT_ID := myproject
REGION := us-central1
PLATFORM := linux/amd64
DOCKER_PORT := 38080

IMAGE = $(HOST)/$(PROJECT_ID)/$(REPO)/$(SERVICE):latest

include Makefile.env

all: gcp-setup cloud-build cloud-run-deploy

copy-keys:
	cp ../../private/gcp_keys/*.json .

docker-build:
	docker build --tag $(SERVICE) --platform $(PLATFORM) .

docker-run:
	docker run -p $(DOCKER_PORT)\:$(PORT) $(SERVICE)

gcp-setup:
	gcloud config set project $(PROJECT_ID)

cloud-build:
	#gcloud auth configure-docker $(HOST)
	gcloud builds submit --tag $(IMAGE) .

cloud-run-deploy:
	gcloud config set run/region $(REGION)
	#gcloud run deploy $(SERVICE) --image $(IMAGE) --platform=managed --allow-unauthenticated --ingress=internal
	gcloud run deploy $(SERVICE) --image $(IMAGE) --platform=managed --allow-unauthenticated

cleanup:
	rm -f *.json
