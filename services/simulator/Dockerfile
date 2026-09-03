FROM golang:1.27.1-alpine3.23 AS build

WORKDIR /src
COPY services/simulator/go.mod ./
RUN go mod download
COPY services/simulator/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -trimpath -ldflags="-s -w -buildid=" -o /out/simulator ./cmd/simulator

FROM scratch

COPY --from=build /out/simulator /simulator

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/simulator"]
