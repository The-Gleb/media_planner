package app

import "media-planner/services/simulator/internal/domain"

type PublicSegment struct {
	ID      string `json:"segment_id"`
	Geo     string `json:"geo"`
	Gender  string `json:"gender"`
	AgeFrom int    `json:"age_from"`
	AgeTo   int    `json:"age_to_exclusive"`
}
type AudienceChannel struct {
	ChannelID domain.ChannelID `json:"channel_id"`
	Segments  []PublicSegment  `json:"segments"`
}
type AudienceCatalog struct {
	EngineVersion string            `json:"engine_version"`
	Digest        string            `json:"world_config_digest"`
	Channels      []AudienceChannel `json:"channels"`
}

func (r *Registry) AudienceCatalog() AudienceCatalog {
	result := AudienceCatalog{r.model.Model.EngineVersion, r.model.Digest, []AudienceChannel{}}
	for _, c := range r.model.Model.Channels {
		ch := AudienceChannel{c.ID, []PublicSegment{}}
		for _, s := range c.Segments {
			ch.Segments = append(ch.Segments, PublicSegment{s.ID, s.Geo, s.Gender, s.AgeFrom, s.AgeTo})
		}
		result.Channels = append(result.Channels, ch)
	}
	return result
}
