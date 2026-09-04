package contract

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/getkin/kin-openapi/openapi3"
)

func TestOpenAPIAndWorldSchemaLoad(t *testing.T) {
	root := filepath.Join("..", "..")
	doc, err := openapi3.NewLoader().LoadFromFile(filepath.Join(root, "specs", "001-adaptive-media-planning", "contracts", "openapi.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if err := doc.Validate(context.Background()); err != nil {
		t.Fatal(err)
	}
	metadataPath := doc.Paths.Find("/v1/world-metadata")
	if metadataPath == nil || metadataPath.Get == nil {
		t.Fatal("OpenAPI is missing GET /v1/world-metadata")
	}
	metadata := doc.Components.Schemas["WorldMetadata"]
	if metadata == nil || metadata.Value == nil || len(metadata.Value.Required) != 4 {
		t.Fatal("WorldMetadata schema is incomplete")
	}
	b, err := os.ReadFile(filepath.Join(root, "specs", "001-adaptive-media-planning", "contracts", "world-config.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(b, &schema); err != nil {
		t.Fatal(err)
	}
	if schema["$schema"] == nil || schema["$defs"] == nil {
		t.Fatal("world schema is incomplete")
	}
}
