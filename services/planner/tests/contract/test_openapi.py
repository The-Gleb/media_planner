from fastapi.testclient import TestClient


def test_generated_openapi_matches_canonical_surface(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["openapi"] == "3.1.2"
    paths = schema["paths"]
    assert set(paths) == {"/v1/plans", "/health/live", "/health/ready"}
    assert paths["/v1/plans"]["post"]["operationId"] == "createMediaPlan"
    assert paths["/health/live"]["get"]["operationId"] == "getPlannerLiveness"
    assert paths["/health/ready"]["get"]["operationId"] == "getPlannerReadiness"
    components = schema["components"]["schemas"]
    for name in (
        "PlanRequest",
        "FixedBudgetPlanRequest",
        "TargetKPIPlanRequest",
        "MediaPlan",
        "Allocation",
        "CampaignState",
        "Problem",
        "Health",
    ):
        assert name in components
    operation = paths["/v1/plans"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PlanRequest"
    }
    for status in ("400", "415", "422", "500"):
        assert "application/problem+json" in operation["responses"][status]["content"]
    assert components["MediaPlan"]["additionalProperties"] is False
    assert components["FixedBudgetPlanRequest"]["additionalProperties"] is False
