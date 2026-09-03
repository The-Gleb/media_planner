package httptransport

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func TestWriteProblemMapsValidation(t *testing.T) {
	t.Parallel()
	err := domain.NewError(domain.CodeValidation, "invalid request").WithField("duration_hours", "out_of_range")
	rr := httptest.NewRecorder()
	writeProblem(rr, httptest.NewRequest(http.MethodPost, "/v1/simulations/x/steps", nil), err)
	if rr.Code != http.StatusUnprocessableEntity || rr.Header().Get("Content-Type") != "application/problem+json" {
		t.Fatalf("status=%d content-type=%q", rr.Code, rr.Header().Get("Content-Type"))
	}
	var p Problem
	if err := json.Unmarshal(rr.Body.Bytes(), &p); err != nil {
		t.Fatal(err)
	}
	if p.Code != string(domain.CodeValidation) || len(p.Errors) != 1 || p.Status != 422 {
		t.Fatalf("unexpected problem: %#v", p)
	}
}

func TestWriteProblemSuppressesInternalDetail(t *testing.T) {
	t.Parallel()
	rr := httptest.NewRecorder()
	writeProblem(rr, httptest.NewRequest(http.MethodGet, "/", nil), errors.New("secret filesystem path"))
	if rr.Code != http.StatusInternalServerError || strings.Contains(rr.Body.String(), "secret") {
		t.Fatalf("leaked internal error: %s", rr.Body.String())
	}
}
