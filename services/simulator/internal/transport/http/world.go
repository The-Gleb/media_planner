package httptransport

import "net/http"

func (a *API) worldMetadata(w http.ResponseWriter, r *http.Request) {
	if !a.readiness.Ready() {
		a.readiness.ReadinessHandler()(w, r)
		return
	}
	writeJSON(w, http.StatusOK, a.registry.WorldMetadata())
}
