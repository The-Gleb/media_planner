package config

import (
	"math"
	"testing"
)

func TestAgeCapacityProfiles(t *testing.T) {
	model, err := LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	weights := map[string][5]int64{
		"social_1":      {15, 15, 10, 7, 5},
		"social_2":      {8, 10, 12, 12, 8},
		"social_3":      {5, 7, 10, 15, 15},
		"marketplace_1": {7, 10, 12, 12, 8},
		"marketplace_2": {7, 10, 12, 12, 8},
		"marketplace_3": {7, 10, 12, 12, 8},
		"programmatic":  {1, 1, 1, 1, 1},
		"sms":           {1, 1, 1, 1, 1},
	}
	ages := map[int]int{13: 0, 19: 1, 31: 2, 46: 3, 60: 4}
	for _, c := range model.Model.Channels {
		w, ok := weights[string(c.ID)]
		if !ok {
			t.Fatalf("missing profile for %s", c.ID)
		}
		var weightSum int64
		for _, v := range w {
			weightSum += v
		}
		for _, geo := range []string{"moscow", "other"} {
			for _, gender := range []string{"female", "male"} {
				var totals [2]int64
				for _, s := range c.Segments {
					if s.Geo == geo && s.Gender == gender {
						totals[0] += s.WarmCapacity
						totals[1] += s.ColdCapacity
					}
				}
				for _, s := range c.Segments {
					if s.Geo != geo || s.Gender != gender {
						continue
					}
					for pool, capacity := range [2]int64{s.WarmCapacity, s.ColdCapacity} {
						want := float64(totals[pool]*w[ages[s.AgeFrom]]) / float64(weightSum)
						if math.Abs(float64(capacity)-want) >= 1 {
							t.Errorf("%s/%s pool %d: capacity %d, expected rounded %.3f", c.ID, s.ID, pool, capacity, want)
						}
					}
				}
			}
		}
	}
}

func TestFiveAgeGroupsAndPreservedPoolCapacity(t *testing.T) {
	model, err := LoadFile("../../configs/world-config.audience.json")
	if err != nil {
		t.Fatal(err)
	}
	totals := map[string][2]int64{
		"social_1":      {489896, 1959592},
		"social_2":      {346408, 1385640},
		"social_3":      {409872, 1639512},
		"programmatic":  {1549192, 6196768},
		"marketplace_1": {379464, 1517904},
		"marketplace_2": {483720, 1934952},
		"marketplace_3": {189720, 758952},
		"sms":           {4000000, 16000000},
	}
	expected := map[[2]int]bool{{13, 19}: true, {19, 31}: true, {31, 46}: true, {46, 60}: true, {60, 131}: true}
	for _, c := range model.Model.Channels {
		if len(c.Segments) != 20 {
			t.Fatalf("%s: expected 20 segments", c.ID)
		}
		var warm, cold int64
		for _, s := range c.Segments {
			if !expected[[2]int{s.AgeFrom, s.AgeTo}] {
				t.Fatalf("unexpected range: %+v", s)
			}
			warm += s.WarmCapacity
			cold += s.ColdCapacity
		}
		if [2]int64{warm, cold} != totals[string(c.ID)] {
			t.Fatalf("%s: capacity changed", c.ID)
		}
		for _, geo := range []string{"moscow", "other"} {
			for _, gender := range []string{"female", "male"} {
				for age := 13; age <= 130; age++ {
					count := 0
					for _, s := range c.Segments {
						if s.Geo == geo && s.Gender == gender && age >= s.AgeFrom && age < s.AgeTo {
							count++
						}
					}
					if count != 1 {
						t.Fatalf("%s %s %s age %d matches %d segments", c.ID, geo, gender, age, count)
					}
				}
			}
		}
	}
}
