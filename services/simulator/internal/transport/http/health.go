package httptransport

import (
	"net/http"
	"sync/atomic"

	"media-planner/services/simulator/internal/domain"
)

type Readiness struct{ ready atomic.Bool }

func (r *Readiness) Set(value bool) { r.ready.Store(value) }
func (r *Readiness) Ready() bool    { return r.ready.Load() }

func (r *Readiness) LivenessHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	}
}

func (r *Readiness) ReadinessHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, req *http.Request) {
		if !r.Ready() {
			writeProblem(w, req, domain.NewError(domain.CodeNotReady, "service is not ready"))
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	}
}
