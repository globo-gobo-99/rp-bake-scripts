group "default" { targets = ["devpod", "testpod"] }
target "common" {
  context = "."
  dockerfile = "Dockerfile"
  platforms = ["linux/amd64"]
  args = { UBUNTU_IMAGE = UBUNTU_IMAGE }
  labels = { "org.opencontainers.image.source" = "https://github.com/gobo-99/dev-pod", "org.opencontainers.image.version" = RELEASE_VERSION, "org.opencontainers.image.revision" = REVISION }
}
target "devpod" {
  inherits = ["common"]
  target = "devpod"
  tags = ["${REGISTRY}/dev-pod:${RELEASE_VERSION}"]
}
target "testpod" {
  inherits = ["common"]
  target = "testpod"
  tags = ["${REGISTRY}/test-pod:${RELEASE_VERSION}"]
}
