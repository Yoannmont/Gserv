import pytest

from accounts.tests.accounts_factories import UserFactory
from games.tests.games_factories import GameFactory
from servers.models import ServerInstance
from servers.tests.servers_factories import ServerConfigurationFactory, ServerInstanceFactory


@pytest.mark.django_db
class TestServerInstanceModel:
    def test_str_method(self):
        server = ServerInstanceFactory(name="Test Server")
        assert str(server) == f"Test Server ({server.game.name})"

    def test_is_running_property_true(self):
        server = ServerInstanceFactory(status=ServerInstance.RUNNING)
        assert server.is_running is True

    def test_is_running_property_false(self):
        server = ServerInstanceFactory(status=ServerInstance.STOPPED)
        assert server.is_running is False

    def test_get_all_port_mappings_main_port_only(self):
        game = GameFactory(default_port="25565", additional_ports=[])
        server = ServerInstanceFactory(game=game, port=30000)

        mappings = server.get_all_port_mappings()

        assert mappings["25565/tcp"] == 30000
        assert mappings["25565/udp"] == 30000

    def test_get_all_port_mappings_main_port_tcp_only(self):
        game = GameFactory(default_port="25565/tcp", additional_ports=[])
        server = ServerInstanceFactory(game=game, port=30000)

        mappings = server.get_all_port_mappings()

        assert mappings["25565/tcp"] == 30000
        assert "25565/udp" not in mappings

    def test_get_all_port_mappings_main_port_udp_only(self):
        game = GameFactory(default_port="25565/udp", additional_ports=[])
        server = ServerInstanceFactory(game=game, port=30000)

        mappings = server.get_all_port_mappings()

        assert mappings["25565/udp"] == 30000
        assert "25565/tcp" not in mappings

    def test_get_all_port_mappings_with_additional_ports(self):
        game = GameFactory(
            default_port="25565",
            additional_ports=[
                {"port": 8080, "protocol": "tcp", "description": "Web"},
                {"port": 27015, "protocol": "both", "description": "Query"},
            ],
        )
        server = ServerInstanceFactory(game=game, port=30000, additional_ports={"8080": 30001, "27015": 30002})

        mappings = server.get_all_port_mappings()

        assert mappings["25565/tcp"] == 30000
        assert mappings["25565/udp"] == 30000
        assert mappings["8080/tcp"] == 30001
        assert mappings["27015/tcp"] == 30002
        assert mappings["27015/udp"] == 30002

    def test_get_all_host_ports(self):
        server = ServerInstanceFactory(port=30000, additional_ports={"8080": 30001, "27015": 30002})

        ports = server.get_all_host_ports()

        assert 30000 in ports
        assert 30001 in ports
        assert 30002 in ports
        assert len(ports) == 3

    def test_get_all_host_ports_without_additional(self):
        server = ServerInstanceFactory(port=30000, additional_ports={})

        ports = server.get_all_host_ports()

        assert ports == [30000]

    def test_is_port_available_free_port(self):
        is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(port=30000)

        assert is_available is True
        assert conflicting_server is None
        assert conflicting_port is None

    def test_is_port_available_used_main_port(self):
        server = ServerInstanceFactory(port=30000, status=ServerInstance.RUNNING)

        is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(port=30000)

        assert is_available is False
        assert conflicting_server == server
        assert conflicting_port == 30000

    def test_is_port_available_used_additional_port(self):
        server = ServerInstanceFactory(port=30000, additional_ports={"8080": 30001}, status=ServerInstance.RUNNING)

        is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(port=30001)

        assert is_available is False
        assert conflicting_server == server
        assert conflicting_port == 30001

    def test_is_port_available_exclude_server(self):
        server = ServerInstanceFactory(port=30000, status=ServerInstance.RUNNING)

        is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(
            port=30000, exclude_server_id=server.id
        )

        assert is_available is True

    def test_is_port_available_stopped_server(self):
        ServerInstanceFactory(port=30000, status=ServerInstance.STOPPED, container_id=None)

        is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(port=30000)

        assert is_available is True

    def test_parse_memory_gigabytes(self):
        result = ServerInstance.parse_memory("4g")
        assert result == 4 * 1024**3

    def test_parse_memory_megabytes(self):
        result = ServerInstance.parse_memory("512m")
        assert result == 512 * 1024**2

    def test_parse_memory_kilobytes(self):
        result = ServerInstance.parse_memory("1024k")
        assert result == 1024 * 1024

    def test_parse_memory_bytes(self):
        result = ServerInstance.parse_memory("1024")
        assert result == 1024

    def test_parse_memory_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid memory format"):
            ServerInstance.parse_memory("invalid")

    def test_parse_memory_empty(self):
        result = ServerInstance.parse_memory("")
        assert result == 0

    def test_get_global_resources_no_servers(self):
        total_memory, total_cpu = ServerInstance.get_global_resources()

        assert total_memory == 0
        assert total_cpu == 0.0

    def test_get_global_resources_with_servers(self):
        server1 = ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=server1, memory_limit="2g", cpu_limit=2.0)

        server2 = ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=server2, memory_limit="4g", cpu_limit=3.0)

        total_memory, total_cpu = ServerInstance.get_global_resources()

        assert total_memory == 6 * 1024**3
        assert total_cpu == 5.0

    def test_get_global_resources_exclude_server(self):
        server1 = ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=server1, memory_limit="2g", cpu_limit=2.0)

        server2 = ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=server2, memory_limit="4g", cpu_limit=3.0)

        total_memory, total_cpu = ServerInstance.get_global_resources(exclude_server_id=server1.id)

        assert total_memory == 4 * 1024**3
        assert total_cpu == 3.0

    def test_check_resources_available_no_limits(self, settings):
        settings.MAX_MEMORY_GLOBAL = None
        settings.MAX_CPU_GLOBAL = None

        is_available, error_message = ServerInstance.check_resources_available("2g", 2.0)

        assert is_available is True
        assert error_message is None

    def test_check_resources_available_within_limits(self, settings):
        settings.MAX_MEMORY_GLOBAL = "10g"
        settings.MAX_CPU_GLOBAL = 8.0

        is_available, error_message = ServerInstance.check_resources_available("2g", 2.0)

        assert is_available is True
        assert error_message is None

    def test_check_resources_available_exceeds_memory_limit(self, settings):
        settings.MAX_MEMORY_GLOBAL = "4g"
        ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")

        is_available, error_message = ServerInstance.check_resources_available("2g", 2.0)

        assert is_available is False
        assert "mémoire" in error_message.lower()

    def test_check_resources_available_exceeds_cpu_limit(self, settings):
        settings.MAX_CPU_GLOBAL = 4.0
        ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=ServerInstance.objects.first(), cpu_limit=3.0)

        is_available, error_message = ServerInstance.check_resources_available("2g", 2.0)

        assert is_available is False
        assert "cpu" in error_message.lower()

    def test_check_resources_available_with_force(self, settings):
        settings.MAX_MEMORY_GLOBAL = "4g"
        ServerInstanceFactory(status=ServerInstance.RUNNING)
        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")

        is_available, error_message = ServerInstance.check_resources_available("2g", 2.0, force=True)

        assert is_available is True
        assert error_message is None

    def test_get_default_configuration_for_game_without_game_config(self):
        game = GameFactory()

        config = ServerInstance.get_default_configuration_for_game(game)

        assert config["memory_limit"] == "2g"
        assert config["cpu_limit"] == 2.0
        assert config["environment_variables"] == {}
        assert config["docker_volumes"] == {}
        assert config["custom_startup_command"] == ""

    def test_get_default_configuration_for_game_with_game_config(self):
        from games.models import GameConfiguration

        game = GameFactory()
        GameConfiguration.objects.create(
            game=game,
            name="Default Config",
            is_default=True,
            config_data={
                "memory_limit": "4g",
                "cpu_limit": 4.0,
                "environment_variables": {"EULA": "TRUE"},
            },
        )

        config = ServerInstance.get_default_configuration_for_game(game)

        assert config["memory_limit"] == "4g"
        assert config["cpu_limit"] == 4.0
        assert config["environment_variables"] == {"EULA": "TRUE"}

    def test_get_default_configuration_for_game_none(self):
        config = ServerInstance.get_default_configuration_for_game(None)

        assert config["memory_limit"] == "2g"
        assert config["cpu_limit"] == 2.0


@pytest.mark.django_db
class TestServerConfigurationModel:
    def test_str_method(self):
        server = ServerInstanceFactory(name="Test Server")
        config = ServerConfigurationFactory(server=server)

        assert str(config) == "Configuration de Test Server"


@pytest.mark.django_db
class TestServerStatusModel:
    def test_str_method(self):
        from servers.models import ServerStatus

        server = ServerInstanceFactory(name="Test Server")
        status_obj = ServerStatus.objects.create(server=server, status=ServerInstance.RUNNING, message="Server started")

        assert server.name in str(status_obj)
        assert ServerInstance.RUNNING in str(status_obj)


@pytest.mark.django_db
class TestServerRoleModel:
    def test_str_method(self):
        from servers.models import ServerRole

        user = UserFactory(username="testuser")
        server = ServerInstanceFactory(name="Test Server")
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_VIEWER)

        assert "testuser" in str(role)
        assert "Test Server" in str(role)

    def test_save_viewer_permissions(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_VIEWER)

        assert role.can_view is True
        assert role.can_edit is False
        assert role.can_control is False
        assert role.can_delete is False

    def test_save_manager_permissions(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_MANAGER)

        assert role.can_view is True
        assert role.can_edit is False
        assert role.can_control is True
        assert role.can_delete is False

    def test_save_editor_permissions(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_EDITOR)

        assert role.can_view is True
        assert role.can_edit is True
        assert role.can_control is True
        assert role.can_delete is False

    def test_save_admin_permissions(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_ADMIN)

        assert role.can_view is True
        assert role.can_edit is True
        assert role.can_control is True
        assert role.can_delete is True

    def test_has_permission_view(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_VIEWER)

        assert role.has_permission("view") is True
        assert role.has_permission("edit") is False

    def test_has_permission_invalid_type(self):
        from servers.models import ServerRole

        user = UserFactory()
        server = ServerInstanceFactory()
        role = ServerRole.objects.create(server=server, user=user, role=ServerRole.ROLE_VIEWER)

        assert role.has_permission("invalid") is False
