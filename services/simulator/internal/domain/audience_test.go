package domain

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestAudienceCanonicalCopy(t *testing.T) {
	a := Audience{"social_1": {SegmentIDs: []string{"b", "a"}}}
	n, err := a.Normalize()
	if err != nil {
		t.Fatal(err)
	}
	a["social_1"].SegmentIDs[0] = "changed"
	if !reflect.DeepEqual(n["social_1"].SegmentIDs, []string{"a", "b"}) {
		t.Fatal(n)
	}
	for _, raw := range []string{`null`, `{}`, `{"a":null}`, `{"a":{"segment_ids":[]}}`, `{"a":{"segment_ids":["x","x"]}}`, `{"a":{"segment_ids":["x"],"temperature":null}}`, `{"a":{"segment_ids":["x"],"extra":1}}`} {
		var v Audience
		if err := json.Unmarshal([]byte(raw), &v); err == nil {
			t.Errorf("accepted %s", raw)
		}
	}
}
