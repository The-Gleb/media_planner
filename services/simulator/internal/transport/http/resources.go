package httptransport

import (
	"net/http"

	"media-planner/services/simulator/internal/app"
	"media-planner/services/simulator/internal/domain"
)

type API struct {
	registry  *app.Registry
	readiness *Readiness
}

func (a *API) reset(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("simulation_id")
	if !uuidPattern.MatchString(id) {
		writeProblem(w, r, domain.NewError(domain.CodeValidation, "invalid simulation_id").WithField("simulation_id", "invalid_uuid"))
		return
	}
	var input simulationConfigDTO
	if err := decodeJSON(w, r, &input); err != nil {
		writeProblem(w, r, err)
		return
	}
	cfg, err := input.domain()
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	state, etag, created, err := a.registry.Reset(id, cfg, r.Header.Get("If-Match"), r.Header.Get("If-None-Match") == "*")
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	w.Header().Set("ETag", etag)
	status := http.StatusOK
	if created {
		status = http.StatusCreated
	}
	writeJSON(w, status, state)
}

func (a *API) current(w http.ResponseWriter, r *http.Request) {
	state, etag, err := a.registry.Current(r.PathValue("simulation_id"))
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	w.Header().Set("ETag", etag)
	writeJSON(w, http.StatusOK, state)
}
func (a *API) delete(w http.ResponseWriter, r *http.Request) {
	if err := a.registry.Delete(r.PathValue("simulation_id"), r.Header.Get("If-Match")); err != nil {
		writeProblem(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
