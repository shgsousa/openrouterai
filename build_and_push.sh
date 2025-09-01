#!/bin/bash

# Build and push the multi-architecture image
echo "Building and pushing the Docker image for architectures: linux/amd64, linux/arm64"

# Ensure buildx is available and create a builder if necessary
if ! docker buildx ls | grep -q "default"; then
    docker buildx create --name multiarch-builder --use
fi

# Build and push the image
docker buildx build --platform "linux/amd64,linux/arm64" --tag "shgsousa/openrouterai:latest" --push .

echo "Docker image pushed to Docker Hub: shgsousa/openrouterai:latest"
