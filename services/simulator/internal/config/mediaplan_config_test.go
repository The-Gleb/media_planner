package config

import (
	"os"
	"testing"

	"media-planner/services/simulator/internal/domain"
)

func TestMediaPlanWorldConfig(t *testing.T) {
	file, err := os.Open("../../configs/world-config.mediaplan.json")
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	loaded, err := Load(file)
	if err != nil {
		t.Fatal(err)
	}
	if got := len(loaded.Model.Channels); got != 8 {
		t.Fatalf("channels=%d, want 8", got)
	}
	want := map[domain.ChannelID]bool{
		"social_1": true, "social_2": true, "social_3": true, "programmatic": true,
		"marketplace_1": true, "marketplace_2": true, "marketplace_3": true, "sms": true,
	}
	for _, channel := range loaded.Model.Channels {
		delete(want, channel.ID)
	}
	if len(want) != 0 {
		t.Fatalf("missing channels: %v", want)
	}
}
