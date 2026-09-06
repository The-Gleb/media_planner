package httptransport

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"media-planner/services/simulator/internal/domain"
)

const maxRequestBytes = 1 << 20

type contextKey string

const traceIDKey contextKey = "trace_id"

func withTraceID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("Traceparent")
		if id == "" {
			buf := make([]byte, 16)
			if _, err := rand.Read(buf); err == nil {
				id = hex.EncodeToString(buf)
			} else {
				id = "unavailable"
			}
		}
		w.Header().Set("X-Trace-ID", id)
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), traceIDKey, id)))
	})
}

func traceID(ctx context.Context) string {
	id, _ := ctx.Value(traceIDKey).(string)
	return id
}

func decodeJSON(w http.ResponseWriter, r *http.Request, dst any) error {
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || mediaType != "application/json" {
		return domainError("unsupported_media_type", "Content-Type must be application/json")
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxRequestBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		var de *domain.Error
		if errors.As(err, &de) {
			return de
		}
		return malformed(err)
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return malformed(fmt.Errorf("trailing JSON value"))
	}
	return nil
}

func domainError(code, message string) error {
	if code == "unsupported_media_type" {
		return domain.NewError(domain.CodeUnsupportedMediaType, message)
	}
	return domain.NewError(domain.CodeValidation, message)
}

func malformed(err error) error { return domain.NewError(domain.CodeMalformedJSON, err.Error()) }

var etagPattern = regexp.MustCompile(`^"([0-9]+)-([a-f0-9]{16})"$`)

func parseETag(value string) (uint64, string, error) {
	match := etagPattern.FindStringSubmatch(strings.TrimSpace(value))
	if match == nil {
		return 0, "", domain.NewError(domain.CodePreconditionFailed, "missing or invalid If-Match")
	}
	revision, err := strconv.ParseUint(match[1], 10, 64)
	if err != nil {
		return 0, "", domain.NewError(domain.CodePreconditionFailed, "invalid If-Match revision")
	}
	return revision, match[2], nil
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
