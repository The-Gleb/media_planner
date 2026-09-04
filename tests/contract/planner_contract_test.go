package contract

import (
	"path/filepath"
	"testing"

	"github.com/getkin/kin-openapi/openapi3"
)

func TestPlannerOpenAPIContract(t *testing.T) {
	root := filepath.Join("..", "..")
	path := filepath.Join(root, "specs", "003-minimal-budget-planner", "contracts", "planner.openapi.yaml")
	doc, err := openapi3.NewLoader().LoadFromFile(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, route := range []string{"/v1/plans", "/health/live", "/health/ready"} {
		if doc.Paths.Find(route) == nil {
			t.Fatalf("planner contract missing %s", route)
		}
	}
	schemas := doc.Components.Schemas
	for _, name := range []string{"PlanRequest", "FixedBudgetPlanRequest", "TargetKPIPlanRequest", "MediaPlan", "Money", "Count", "Problem"} {
		if schemas[name] == nil || schemas[name].Value == nil {
			t.Fatalf("planner contract missing schema %s", name)
		}
	}
	if schemas["Money"].Value.Pattern == "" || schemas["Count"].Value.Pattern == "" {
		t.Fatal("exact money/count string patterns are required")
	}
}
