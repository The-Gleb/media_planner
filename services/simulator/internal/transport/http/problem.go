package httptransport

import (
	"encoding/json"
	"errors"
	"net/http"

	"media-planner/services/simulator/internal/domain"
)

type Problem struct {
	Type     string              `json:"type"`
	Title    string              `json:"title"`
	Status   int                 `json:"status"`
	Detail   string              `json:"detail,omitempty"`
	Instance string              `json:"instance,omitempty"`
	Code     string              `json:"code"`
	TraceID  string              `json:"trace_id,omitempty"`
	Errors   []domain.FieldError `json:"errors,omitempty"`
}

func writeProblem(w http.ResponseWriter, r *http.Request, err error) {
	status, title, code, detail, fields := mapProblem(err)
	p := Problem{
		Type: "https://media-planner.local/problems/" + code, Title: title, Status: status,
		Detail: detail, Instance: r.URL.Path, Code: code, TraceID: traceID(r.Context()), Errors: fields,
	}
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(p)
}

func mapProblem(err error) (int, string, string, string, []domain.FieldError) {
	var de *domain.Error
	if !errors.As(err, &de) {
		return http.StatusInternalServerError, "Internal server error", string(domain.CodeInternal), "The request could not be completed", nil
	}
	status := http.StatusInternalServerError
	title := "Internal server error"
	switch de.Code {
	case domain.CodeValidation:
		status, title = http.StatusUnprocessableEntity, "Request validation failed"
	case domain.CodeMalformedJSON:
		status, title = http.StatusBadRequest, "Malformed JSON request"
	case domain.CodeUnsupportedMediaType:
		status, title = http.StatusUnsupportedMediaType, "Unsupported media type"
	case domain.CodeInvalidConfig:
		status, title = http.StatusInternalServerError, "Simulator configuration is invalid"
	case domain.CodeNotFound:
		status, title = http.StatusNotFound, "Simulation not found"
	case domain.CodeGone:
		status, title = http.StatusGone, "Simulation is gone"
	case domain.CodeConflict, domain.CodeActiveLimit, domain.CodeSimulationFinished, domain.CodeStepIDReused:
		status, title = http.StatusConflict, "Simulation state conflict"
	case domain.CodePreconditionFailed:
		status, title = http.StatusPreconditionFailed, "State precondition failed"
	case domain.CodeNotReady:
		status, title = http.StatusServiceUnavailable, "Service is not ready"
	}
	detail := de.Message
	if status >= 500 {
		detail = "The request could not be completed"
	}
	return status, title, string(de.Code), detail, de.Fields
}
