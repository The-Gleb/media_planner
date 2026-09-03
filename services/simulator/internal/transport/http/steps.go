package httptransport

import (
	"net/http"

	"media-planner/services/simulator/internal/domain"
)

func (a *API) step(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("simulation_id")
	if !uuidPattern.MatchString(id) {
		writeProblem(w, r, domain.NewError(domain.CodeValidation, "invalid simulation_id").WithField("simulation_id", "invalid_uuid"))
		return
	}
	var input stepRequestDTO
	if err := decodeJSON(w, r, &input); err != nil {
		writeProblem(w, r, err)
		return
	}
	actions, err := input.domainActions()
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	result, etag, err := a.registry.Step(id, input.StepID, r.Header.Get("If-Match"), actions)
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	w.Header().Set("ETag", etag)
	writeJSON(w, http.StatusOK, result)
}
