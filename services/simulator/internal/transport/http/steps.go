package httptransport

import (
	"net/http"
)

func (a *API) step(w http.ResponseWriter, r *http.Request) {
	id, err := parseSimulationID(r.PathValue("simulation_id"))
	if err != nil {
		writeProblem(w, r, err)
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
	result, etag, err := a.registry.Step(id, input.StepID, r.Header.Get("If-Match"), actions, input.Audience)
	if err != nil {
		writeProblem(w, r, err)
		return
	}
	w.Header().Set("ETag", etag)
	writeJSON(w, http.StatusOK, result)
}
