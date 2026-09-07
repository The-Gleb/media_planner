package simulation

// Cohorts count recipients, not message segments. A recipient belongs to at
// most one cohort: unavailable supply cannot be allocated again until return.
type smsCohort struct {
	ReturnHour int
	Count      int64
}

func activeSMSCooldown(cohorts []smsCohort, hour int) ([]smsCohort, int64) {
	active := make([]smsCohort, 0, len(cohorts))
	var unavailable int64
	for _, c := range cohorts {
		if c.ReturnHour > hour {
			active = append(active, c)
			unavailable += c.Count
		}
	}
	return active, unavailable
}
