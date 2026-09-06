package domain

import (
	"bytes"
	"encoding/json"
	"io"
	"sort"
)

type ChannelAudience struct {
	SegmentIDs []string `json:"segment_ids"`
}
type Audience map[ChannelID]ChannelAudience

func (a Audience) Normalize() (Audience, error) {
	if a == nil {
		return nil, nil
	}
	if len(a) == 0 || len(a) > 20 {
		return nil, NewError(CodeValidation, "invalid audience").WithField("audience", "empty_or_too_large")
	}
	result := make(Audience, len(a))
	for id, s := range a {
		field := "audience." + string(id)
		if id.Validate() != nil || len(s.SegmentIDs) == 0 || len(s.SegmentIDs) > 128 {
			return nil, NewError(CodeValidation, "invalid audience").WithField(field, "invalid_selection")
		}
		s.SegmentIDs = append([]string(nil), s.SegmentIDs...)
		sort.Strings(s.SegmentIDs)
		for i, v := range s.SegmentIDs {
			if ChannelID(v).Validate() != nil || (i > 0 && s.SegmentIDs[i-1] == v) {
				return nil, NewError(CodeValidation, "invalid audience").WithField(field+".segment_ids", "invalid_or_duplicate")
			}
		}
		result[id] = s
	}
	return result, nil
}

func (a *Audience) UnmarshalJSON(data []byte) error {
	type wire struct {
		SegmentIDs []string `json:"segment_ids"`
	}
	var items map[ChannelID]*wire
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&items); err != nil {
		return err
	}
	if err := dec.Decode(new(any)); err != io.EOF {
		return NewError(CodeValidation, "invalid audience")
	}
	if len(items) == 0 {
		return NewError(CodeValidation, "invalid audience").WithField("audience", "must_be_nonempty_object")
	}
	out := make(Audience, len(items))
	for id, item := range items {
		if item == nil {
			return NewError(CodeValidation, "invalid audience").WithField("audience."+string(id), "must_be_object")
		}
		out[id] = ChannelAudience{SegmentIDs: item.SegmentIDs}
	}
	normalized, err := out.Normalize()
	if err == nil {
		*a = normalized
	}
	return err
}
