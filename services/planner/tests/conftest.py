"""Фикстуры: каталог из конфига симулятора и живой Go-симулятор.

Симулятор берётся из SIMULATOR_URL, а если переменной нет — запускается собранный бинарник
services/simulator/bin/simulator на свободном порту (сборка: `go build -o bin/simulator ./cmd/simulator`).
Без того и другого интеграционные тесты пропускаются.
"""

import os
import pathlib
import socket
import subprocess
import typing

import pytest

from mediaplan import catalog as catalog_module
from mediaplan.contracts import Brief, Catalog
from mediaplan.simulator_client import SimulatorClient, wait_until_ready


SIMULATOR_BINARY: typing.Final = pathlib.Path(__file__).resolve().parents[2] / "simulator" / "bin" / "simulator"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def simulator_url() -> typing.Iterator[str]:
    configured = os.environ.get("SIMULATOR_URL")
    if configured:
        if not wait_until_ready(configured):
            pytest.skip(f"симулятор по SIMULATOR_URL={configured} не готов")
        yield configured
        return
    if not SIMULATOR_BINARY.exists():
        pytest.skip(f"нет бинарника симулятора {SIMULATOR_BINARY} и не задан SIMULATOR_URL")
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(  # noqa: S603
        [str(SIMULATOR_BINARY)],
        env={
            **os.environ,
            "SIMULATOR_ADDR": f"127.0.0.1:{port}",
            "SIMULATOR_CONFIG": str(catalog_module.resolve_world_config_path()),
            "SIMULATOR_RELAX_PRECONDITIONS": "false",
            "SIMULATOR_LOG_LEVEL": "warn",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_until_ready(url):
            pytest.fail("симулятор не поднялся")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return catalog_module.build_catalog(catalog_module.load_world_config())


@pytest.fixture
def client(catalog: Catalog, simulator_url: str) -> typing.Iterator[SimulatorClient]:
    with SimulatorClient(catalog.channel_ids, base_url=simulator_url) as simulator_client:
        yield simulator_client


@pytest.fixture
def short_brief() -> Brief:
    return Brief(budget_rub=800_000.0, horizon_days=14, objective="conversions")
