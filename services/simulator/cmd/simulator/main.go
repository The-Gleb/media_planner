package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	_ "time/tzdata"

	"media-planner/services/simulator/internal/app"
	"media-planner/services/simulator/internal/config"
	httptransport "media-planner/services/simulator/internal/transport/http"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "healthcheck" {
		if err := healthcheck(os.Args[2:]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: parseLevel(os.Getenv("SIMULATOR_LOG_LEVEL"))}))
	slog.SetDefault(logger)
	configPath := envOr("SIMULATOR_CONFIG", "configs/world-config.json")
	loaded, err := config.LoadFile(configPath)
	if err != nil {
		logger.Error("load world config", "error", err)
		os.Exit(1)
	}
	readiness := &httptransport.Readiness{}
	registryOptions := []app.RegistryOption{}
	if envBool("SIMULATOR_RELAX_PRECONDITIONS") {
		registryOptions = append(registryOptions, app.WithoutPreconditions())
	}
	registry := app.NewRegistry(loaded, registryOptions...)
	handler := httptransport.NewHandler(registry, readiness)
	server := httptransport.NewHTTPServer(envOr("SIMULATOR_ADDR", ":8080"), handler)
	readiness.Set(true)
	errCh := make(chan error, 1)
	go func() {
		logger.Info("simulator listening", "addr", server.Addr, "engine_version", loaded.Model.EngineVersion, "world_config_digest", loaded.Digest)
		errCh <- server.ListenAndServe()
	}()
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	select {
	case sig := <-signals:
		logger.Info("shutdown signal", "signal", sig.String())
	case err := <-errCh:
		if err != nil && err != http.ErrServerClosed {
			logger.Error("server failed", "error", err)
			os.Exit(1)
		}
	}
	readiness.Set(false)
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
		os.Exit(1)
	}
}

func healthcheck(args []string) error {
	fs := flag.NewFlagSet("healthcheck", flag.ContinueOnError)
	url := fs.String("url", "http://127.0.0.1:8080/health/ready", "health URL")
	if err := fs.Parse(args); err != nil {
		return err
	}
	client := http.Client{Timeout: 1500 * time.Millisecond}
	resp, err := client.Get(*url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health status %d", resp.StatusCode)
	}
	return nil
}
func envOr(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
func envBool(key string) bool {
	switch os.Getenv(key) {
	case "1", "true", "TRUE", "yes", "YES":
		return true
	default:
		return false
	}
}
func parseLevel(value string) slog.Level {
	switch value {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
