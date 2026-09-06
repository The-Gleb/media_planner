package httptransport

import (
	"net/http"
	"time"

	"media-planner/services/simulator/internal/app"
)

func NewHandler(registry *app.Registry, readiness *Readiness) http.Handler {
	api := &API{registry: registry, readiness: readiness}
	observer := NewObserver()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health/live", readiness.LivenessHandler())
	mux.HandleFunc("GET /health/ready", readiness.ReadinessHandler())
	mux.HandleFunc("GET /v1/world-metadata", api.worldMetadata)
	mux.HandleFunc("GET /v1/audience-segments", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, http.StatusOK, registry.AudienceCatalog()) })
	mux.HandleFunc("PUT /v1/simulations/{simulation_id}", api.reset)
	mux.HandleFunc("GET /v1/simulations/{simulation_id}/current-hour", api.current)
	mux.HandleFunc("POST /v1/simulations/{simulation_id}/steps", api.step)
	mux.HandleFunc("DELETE /v1/simulations/{simulation_id}", api.delete)
	mux.Handle("GET /metrics", observer.Handler())
	return withTraceID(observer.Wrap(mux))
}

func NewHTTPServer(addr string, handler http.Handler) *http.Server {
	return &http.Server{Addr: addr, Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 1 << 20}
}
