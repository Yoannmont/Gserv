import random
import time
from unittest.mock import MagicMock

import docker


class ContainerMockup:
    def __init__(
        self,
        container_id: str,
        name: str,
        image: str,
        ports: dict,
        environment: dict,
        volumes: dict,
        memory_limit: str,
        cpu_limit: float,
        restart_policy: dict,
    ):
        self.id = container_id
        self.name = name
        self.image = MagicMock()
        self.image.tags = [image]
        self.status = "created"
        self.attrs = {
            "Id": container_id,
            "Name": f"/{name}",
            "Config": {
                "Image": image,
                "Env": [f"{k}={v}" for k, v in environment.items()],
            },
            "HostConfig": {
                "PortBindings": {port: [{"HostPort": str(host_port)}] for port, host_port in ports.items()},
                "Binds": [f"{host_path}:{bind['bind']}:{bind.get('mode', 'rw')}" for host_path, bind in volumes.items()],
                "Memory": self._parse_memory(memory_limit),
                "NanoCpus": int(cpu_limit * 1e9),
                "RestartPolicy": restart_policy,
            },
            "State": {
                "Status": self.status,
            },
        }
        self._logs = []
        self._start_time = None
        self._stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 0},
                "system_cpu_usage": 0,
                "online_cpus": int(cpu_limit),
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 0},
                "system_cpu_usage": 0,
            },
            "memory_stats": {
                "usage": 0,
                "limit": self._parse_memory(memory_limit),
            },
            "networks": {"eth0": {"rx_bytes": 0, "tx_bytes": 0}},
        }

    @staticmethod
    def _parse_memory(memory_limit: str):
        if memory_limit.endswith("g"):
            return int(float(memory_limit[:-1]) * 1024 * 1024 * 1024)
        elif memory_limit.endswith("m"):
            return int(float(memory_limit[:-1]) * 1024 * 1024)
        elif memory_limit.endswith("k"):
            return int(float(memory_limit[:-1]) * 1024)
        else:
            return int(memory_limit)

    def start(self):
        if self.status == "running":
            return
        self.status = "running"
        self.attrs["State"]["Status"] = "running"
        self._start_time = time.time()
        self._add_log("Container started")

    def stop(self, timeout: int = 30):
        if self.status == "stopped":
            return
        self.status = "exited"
        self.attrs["State"]["Status"] = "exited"
        self._add_log("Container stopped")

    def restart(self, timeout: int = 30):
        self.stop(timeout)
        self.start()

    def remove(self, force: bool = False, v: bool = False):
        if self.status == "running" and not force:
            raise docker.errors.APIError("Cannot remove running container", 409, None)
        self.status = "removed"
        self.attrs["State"]["Status"] = "removed"

    def logs(self, stream: bool = False, follow: bool = False, tail: int = 100, timestamps: bool = True):
        if self.status == "removed":
            raise docker.errors.NotFound(f"Container {self.id} not found")

        log_lines = self._logs[-tail:] if tail > 0 and len(self._logs) > tail else self._logs

        if timestamps:
            formatted_logs = [f"2024-01-01T12:00:00.000000000Z - {line}" for line in log_lines]
        else:
            formatted_logs = log_lines

        if stream:
            return self._log_stream(formatted_logs)  # Yielder
        else:
            return "\n".join(formatted_logs).encode("utf-8")  # Return all logs as bytes

    def _log_stream(self, formatted_logs):
        for line in formatted_logs:
            yield (line + "\n").encode("utf-8")

    def exec_run(self, command: str):
        """Execute a command in the container"""
        if self.status != "running":
            raise docker.errors.APIError("Container is not running", 409, None)

        result = MagicMock()
        result.output = f"Command executed: {command}".encode()
        result.exit_code = 0
        return result

    def stats(self, stream: bool = False):
        if self.status == "removed":
            raise docker.errors.NotFound(f"Container {self.id} not found")

        if self.status != "running":
            raise docker.errors.APIError("Container is not running", 409, None)

        if self._start_time:
            uptime = time.time() - self._start_time
            self._stats["cpu_stats"]["cpu_usage"]["total_usage"] = int(uptime * 1e9 * 0.5)
            self._stats["cpu_stats"]["system_cpu_usage"] = int(uptime * 1e9)
            self._stats["memory_stats"]["usage"] = int(self._stats["memory_stats"]["limit"] * 0.3)

        if stream:
            return self._stats_stream()
        else:
            return self._stats.copy()

    def _stats_stream(self):
        while True:
            yield self._stats.copy()

    def _add_log(self, message: str):
        self._logs.append(message)
        if len(self._logs) > 10000:
            self._logs = self._logs[-10000:]

    def reload(self):
        pass


class DockerClientMockup:
    def __init__(self):
        self.containers = ContainerCollectionMockup(self)
        self.images = ImagesCollection()
        self._container_counter = 0

    def ping(self):
        return True

    def _generate_container_id(self):
        self._container_counter += 1
        return "yo" * 31 + f"{random.randint(0, 99):02}"


class ContainerCollectionMockup:
    def __init__(self, client: DockerClientMockup):
        self._client = client
        self._containers = {}
        self._containers_by_name = {}

    def create(
        self,
        image: str,
        name: str,
        ports: dict | None = None,
        environment: dict | None = None,
        volumes: dict | None = None,
        mem_limit: str = "2g",
        nano_cpus: int = 2000000000,
        restart_policy: dict | None = None,
        detach: bool = True,
        stdin_open: bool = False,
        tty: bool = False,
    ):
        container_id = self._client._generate_container_id()

        if name in self._containers_by_name and self._containers_by_name[name].status != "removed":
            raise docker.errors.APIError(f"Conflict. The container name '{name}' is already in use", 409, None)

        container = ContainerMockup(
            container_id=container_id,
            name=name,
            image=image,
            ports=ports or {},
            environment=environment or {},
            volumes=volumes or {},
            memory_limit=mem_limit,
            cpu_limit=nano_cpus / 1e9,
            restart_policy=restart_policy or {"Name": "unless-stopped"},
        )

        self._containers[container_id] = container
        self._containers_by_name[name] = container

        return container

    def get(self, container_id: str):
        if container_id in self._containers:
            container = self._containers[container_id]
            if container.status == "removed":
                raise docker.errors.NotFound(f"No such container: {container_id}")
            return container

        if container_id in self._containers_by_name:
            container = self._containers_by_name[container_id]
            if container.status == "removed":
                raise docker.errors.NotFound(f"No such container: {container_id}")
            return container

        raise docker.errors.NotFound(f"No such container: {container_id}")

    def list(self, all: bool = False):
        if all:
            return [c for c in self._containers.values() if c.status != "removed"]
        else:
            return [c for c in self._containers.values() if c.status == "running"]

    def prune(self):
        removed = []
        for container_id, container in self._containers.items():
            if container.status in ("exited", "stopped"):
                removed.append(container_id)
                del self._containers[container_id]
                if container.name in self._containers_by_name:
                    del self._containers_by_name[container.name]

        return {"ContainersDeleted": removed}


class ImagesCollection:
    def __init__(self):
        self._images = set()

    def pull(self, image: str):
        self._images.add(image)
        return
