# Deploying to Kubernetes

## The Basics
Here is an example Github Action that deploys the SOAD trading system helm chart to a Digital Ocean Kubernetes cluster. This action is triggered when a new release is created. The action will install the helm chart and update the deployment with the new image. It should be nearly identical for other cloud providers.

- Make sure to replace the `DO_KUBECONFIG` secret with your own DigitalOcean Kubernetes cluster kubeconfig.
- values.yaml is your own values file for the helm chart (see example).

```yaml
name: Deploy to DigitalOcean Kubernetes

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v2

    - name: Install kubectl
      run: |
        curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
        chmod +x ./kubectl
        sudo mv ./kubectl /usr/local/bin/kubectl

    - name: Install Helm
      run: |
        curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash

    - name: Set up kubeconfig
      run: |
        mkdir -p $HOME/.kube
        echo "${{ secrets.DO_KUBECONFIG }}" > $HOME/.kube/config
        chmod 600 $HOME/.kube/config

    - name: Deploy with Helm
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        git clone https://github.com/r0fls/soad.git
        cd soad/helm-chart
        helm repo add stable https://charts.helm.sh/stable
        helm repo update
        helm dependency build
        helm upgrade --install trading-system . -f ../../values.yaml
```

## Configuring Ingress and Cert Manager

Additionally, if you want a public domain with SSH you can deploy the ingress-nginx controller and cert-manager to your cluster. Here is an example of how to do that:

```yaml
name: Deploy Infra to DigitalOcean Kubernetes

on:
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v2

    - name: Install kubectl
      run: |
        curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
        chmod +x ./kubectl
        sudo mv ./kubectl /usr/local/bin/kubectl

    - name: Install Helm
      run: |
        curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash

    - name: Set up kubeconfig
      run: |
        mkdir -p $HOME/.kube
        echo "${{ secrets.DO_KUBECONFIG }}" > $HOME/.kube/config
        chmod 600 $HOME/.kube/config

    - name: Deploy ingress nginx with Helm
      run: |
        helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
        helm repo update
        helm upgrade --install nginx-ingress ingress-nginx/ingress-nginx --set controller.publishService.enabled=true

    - name: Deploy Cert Manager
      run: |
        helm repo add jetstack https://charts.jetstack.io
        helm repo update
        kubectl create namespace cert-manager | echo "Cert manager namespace already exists"
        kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v1.11.0/cert-manager.crds.yaml
        helm upgrade --install cert-manager jetstack/cert-manager --namespace cert-manager --version v1.8.0

    - name: Deploy YAML
      run: |
        kubectl create -f do-k8s/
```

## Releasing A Custom Trading Image

Finally, here is an example of releasing the custom trading image containing your strategies to the Kubernetes cluster.
> NOTE: you will need to have the trading image pointing to the image in your private registry, and the pullSecret configured to allow access from the cluster.

```yaml
name: Release Trading Image

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v1

      - name: Install doctl
        run: |
          curl -sL https://github.com/digitalocean/doctl/releases/download/v1.64.0/doctl-1.64.0-linux-amd64.tar.gz | tar -xzv
          sudo mv doctl /usr/local/bin

      - name: Authenticate doctl
        run: doctl auth init -t ${{ secrets.DO_API_TOKEN }}

      - name: Log in to DigitalOcean Container Registry
        run: echo "${{ secrets.DO_API_TOKEN }}" | docker login registry.digitalocean.com -u "doctl" --password-stdin

      - name: Lint Strategy files with flake8
        run: |
          # Stop the build if there are Python syntax errors or undefined names
          pip install flake8
          flake8 soad-deploy/ --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Build and push Docker image
        uses: docker/build-push-action@v2
        with:
          context: ./soad-deploy/
          file: ./soad-deploy/Dockerfile
          tags: registry.digitalocean.com/<YOUR_REGISTRY>/soad-trading-system:latest
          push: true
          cache-from: type=local,src=/tmp/.buildx-cache
          cache-to: type=local,dest=/tmp/.buildx-cache
          build-args: |
            BUILDKIT_INLINE_CACHE=1

      - name: Install kubectl
        run: |
          curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
          chmod +x ./kubectl
          sudo mv ./kubectl /usr/local/bin/kubectl

      - name: Set up kubeconfig
        run: |
          mkdir -p $HOME/.kube
          echo "${{ secrets.DO_KUBECONFIG }}" > $HOME/.kube/config
          chmod 600 $HOME/.kube/config

      - name: Deploy to Kubernetes
        run: kubectl delete pod -l app.kubernetes.io/name=system-of-a-dow,component=trading --namespace default
```
