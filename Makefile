SERVICE = gcp-networking
RUNTIME := python314
PORT = 8080
DOCKER_PORT := 38080
PLATFORM := linux/amd64
GCP_REGION := us-central1
GCP_ZONE := us-central1-a
GCP_HOST := us-docker.pkg.dev
GCP_REPO := cloudbuild
GCP_PROJECT_ID := your-project-id
GCP_EMAIL := my-account@your-project-id.iam.gserviceaccount.com
GCP_KEYFILE := /home/mykeyfile.json

include .env

GCP_IMAGE = $(GCP_HOST)/$(GCP_PROJECT_ID)/$(GCP_REPO)/$(SERVICE):latest

all: docker
docker: docker-build docker-run
gcp: gcp-auth gcp-config gcp-build

docker-build:
	docker build --tag $(SERVICE) --platform $(PLATFORM) .

docker-run:
	docker run -p $(DOCKER_PORT)\:$(PORT) $(SERVICE)

docker-push:
	docker push $(SERVICE)

gcp-config:
	gcloud config set project $(GCP_PROJECT_ID)
	gcloud config set core/project $(GCP_PROJECT_ID)
	gcloud config set compute/region $(GCP_REGION)
	gcloud config set compute/zone $(GCP_ZONE)

gcp-auth:
	gcloud auth configure-docker $(GCP_HOST)
	gcloud config set account $(GCP_EMAIL)
	gcloud auth login --cred-file="$(GCP_KEYFILE)"
	gcloud auth activate-service-account $(GCP_EMAIL) --key-file="$(GCP_KEYFILE)"
	#gcloud auth application-default login $(GCP_EMAIL) --client-id-file="$(GCP_KEYFILE)"
	#gcloud auth application-default set-quota-project $(GCP_PROJECT_ID)
	export GOOGLE_APPLICATION_CREDENTIALS="$(GCP_KEYFILE)"

gcp-build:
	gcloud builds submit --tag $(GCP_IMAGE) .

gcp-files:
	gcloud storage cp *.txt "gs://$(GCP_BUCKET)" > /dev/null

gcp-instance:
	gcloud compute instances create-with-container $(SERVICE) \
	--zone=$(GCP_ZONE) --machine-type=$(GCP_MACHINE_TYPE) \
	--container-image=$(GCP_IMAGE) --container-env=GCP_BUCKET=$(GCP_BUCKET) \
	--container-restart-policy=Always

gcp-instance2:
	gcloud compute instances create $(SERVICE) \
	--zone=$(GCP_ZONE) --machine-type=$(GCP_MACHINE_TYPE) \
	--image=$(GCP_IMAGE)

gcp-cloudrun:
	gcloud config set run/region $(GCP_REGION)
	gcloud run deploy $(SERVICE) --image $(GCP_IMAGE) --port $(PORT) --platform=managed --allow-unauthenticated
