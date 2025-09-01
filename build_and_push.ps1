# Build and push the multi-architecture image
Write-Host "Building and pushing the Docker image for architectures: $Platforms"

# Ensure buildx is available and create a builder if necessary
if (-not (docker buildx ls | Select-String -Pattern "default")) {
    docker buildx create --name multiarch-builder --use
}

# Build and push the image
docker buildx build --platform "linux/amd64,linux/arm64" --tag "shgsousa/openrouterai:latest" --push .

Write-Host "Docker image pushed to Docker Hub: shgsousa/openrouterai:latest"