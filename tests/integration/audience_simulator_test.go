package integration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"reflect"
	"strings"
	"testing"
)

func TestAudienceSimulatorLifecycle(t *testing.T) {
	if os.Getenv("RUN_AUDIENCE_TESTS") != "1" {
		t.Skip("requires isolated segmented simulator")
	}
	base := strings.TrimRight(os.Getenv("SIMULATOR_BASE_URL"), "/")
	if base == "" {
		t.Fatal("SIMULATOR_BASE_URL required")
	}
	client := &http.Client{}
	id := "audience-integration"
	path := base + "/v1/simulations/" + id
	call := func(method, url string, body any, etag string) (int, string, map[string]any) {
		t.Helper()
		raw, _ := json.Marshal(body)
		req, _ := http.NewRequest(method, url, bytes.NewReader(raw))
		req.Header.Set("Content-Type", "application/json")
		if etag == "*" {
			req.Header.Set("If-None-Match", "*")
		} else {
			req.Header.Set("If-Match", etag)
		}
		res, err := client.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer res.Body.Close()
		var result map[string]any
		data, _ := io.ReadAll(res.Body)
		if len(data) > 0 {
			if err := json.Unmarshal(data, &result); err != nil {
				t.Fatal(string(data), err)
			}
		}
		return res.StatusCode, res.Header.Get("ETag"), result
	}
	_, _, catalog := call("GET", base+"/v1/audience-segments", nil, "")
	if catalog["engine_version"] != "sim-v2-delivery" {
		t.Fatal("not segmented")
	}
	audience := map[string]any{"social_1": map[string]any{"segment_ids": []string{"moscow_female_19_30"}}}
	cfg := map[string]any{"world_seed": "42", "campaign_seed": "77", "start_hour": "2026-09-03T06:00:00Z", "duration_hours": 168, "time_zone": "UTC", "audience": audience}
	code, etag, result := call("PUT", path, cfg, "*")
	if code != 201 {
		t.Fatal(code, result)
	}
	_, beforeTag, before := call("GET", path+"/current-hour", nil, "")
	bad := map[string]any{"step_id": "99999999-1111-4111-8111-111111111111", "actions": []any{}, "audience": map[string]any{"social_1": map[string]any{"segment_ids": []string{"moscow_female_19_30"}, "temperature": "warm"}}}
	if status, _, _ := call("POST", path+"/steps", bad, etag); status != 400 {
		t.Fatal("temperature accepted", status)
	}
	bad["audience"] = map[string]any{"social_1": map[string]any{"segment_ids": []string{"moscow_female_31_45"}}}
	if status, _, _ := call("POST", path+"/steps", bad, etag); status != 422 {
		t.Fatal("mismatch accepted", status)
	}
	_, afterTag, after := call("GET", path+"/current-hour", nil, "")
	if beforeTag != afterTag || !reflect.DeepEqual(before, after) {
		t.Fatal("non-atomic rejection")
	}
	defer func() {
		status, current, _ := call("GET", path+"/current-hour", nil, "")
		if status == 200 {
			call("DELETE", path, nil, current)
		}
	}()
	history := []any{}
	for run := 0; run < 2; run++ {
		for hour := 0; hour < 168; hour++ {
			body := map[string]any{"step_id": fmt.Sprintf("%08x-1111-4111-8111-111111111111", hour+1), "actions": []any{map[string]any{"channel_id": "social_1", "budget_cap": "1000.000000"}}, "audience": audience}
			code, next, result := call("POST", path+"/steps", body, etag)
			if code != 200 {
				t.Fatal(code, result)
			}
			etag = next
			if run == 0 {
				history = append(history, result["observations"])
			} else if !reflect.DeepEqual(history[hour], result["observations"]) {
				t.Fatal("non reproducible", hour)
			}
			if hour == 0 {
				code, replayTag, replay := call("POST", path+"/steps", body, etag)
				if code != 200 || replayTag != etag || !reflect.DeepEqual(replay, result) {
					t.Fatal("replay")
				}
			}
		}
		if run == 0 {
			code, next, result := call("PUT", path, cfg, etag)
			if code != 200 {
				t.Fatal(code, result)
			}
			etag = next
		}
	}
}
