package httptransport

import (
	"fmt"
	"log/slog"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

type metricValue struct {
	Count           uint64
	DurationSeconds float64
}
type Observer struct {
	mu       sync.Mutex
	requests map[string]metricValue
}

func NewObserver() *Observer { return &Observer{requests: make(map[string]metricValue)} }

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}
func (w *statusWriter) Write(p []byte) (int, error) {
	if w.status == 0 {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(p)
}

func (o *Observer) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w}
		next.ServeHTTP(sw, r)
		if sw.status == 0 {
			sw.status = http.StatusOK
		}
		route := r.Pattern
		if route == "" {
			route = "unmatched"
		}
		statusClass := strconv.Itoa(sw.status/100) + "xx"
		key := r.Method + "|" + route + "|" + statusClass
		duration := time.Since(start)
		o.mu.Lock()
		value := o.requests[key]
		value.Count++
		value.DurationSeconds += duration.Seconds()
		o.requests[key] = value
		o.mu.Unlock()
		slog.Info("http request", "method", r.Method, "route", route, "status", sw.status, "duration_ms", duration.Milliseconds(), "trace_id", traceID(r.Context()))
	})
}

func (o *Observer) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		o.mu.Lock()
		snapshot := make(map[string]metricValue, len(o.requests))
		for k, v := range o.requests {
			snapshot[k] = v
		}
		o.mu.Unlock()
		keys := make([]string, 0, len(snapshot))
		for k := range snapshot {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		for _, key := range keys {
			parts := strings.Split(key, "|")
			v := snapshot[key]
			fmt.Fprintf(w, "simulator_http_requests_total{method=%q,route=%q,status_class=%q} %d\n", parts[0], parts[1], parts[2], v.Count)
			fmt.Fprintf(w, "simulator_http_request_duration_seconds_sum{method=%q,route=%q} %.9f\n", parts[0], parts[1], v.DurationSeconds)
			fmt.Fprintf(w, "simulator_http_request_duration_seconds_count{method=%q,route=%q} %d\n", parts[0], parts[1], v.Count)
		}
	})
}
