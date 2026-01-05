import pytest

from games.tests.games_factories import GameFactory


@pytest.mark.django_db
class TestGameModel:
    def test_parse_default_port_without_protocol(self):
        """Test parsing default_port without protocol (backward compatibility)"""
        game = GameFactory(default_port="25565")
        port_num, protocol = game.parse_default_port()
        assert port_num == 25565
        assert protocol == "both"

    def test_parse_default_port_with_tcp(self):
        """Test parsing default_port with TCP protocol"""
        game = GameFactory(default_port="25565/tcp")
        port_num, protocol = game.parse_default_port()
        assert port_num == 25565
        assert protocol == "tcp"

    def test_parse_default_port_with_udp(self):
        """Test parsing default_port with UDP protocol"""
        game = GameFactory(default_port="25565/udp")
        port_num, protocol = game.parse_default_port()
        assert port_num == 25565
        assert protocol == "udp"

    def test_parse_default_port_case_insensitive(self):
        """Test parsing default_port with uppercase protocol"""
        game = GameFactory(default_port="25565/TCP")
        port_num, protocol = game.parse_default_port()
        assert port_num == 25565
        assert protocol == "tcp"

    def test_parse_default_port_invalid_format(self):
        """Test parsing default_port with invalid format"""
        game = GameFactory(default_port="invalid")
        with pytest.raises(ValueError, match="Invalid default_port format"):
            game.parse_default_port()

    def test_get_all_ports_without_protocol(self):
        """Test get_all_ports when default_port has no protocol"""
        game = GameFactory(default_port="25565", additional_ports=[])
        ports = game.get_all_ports()
        assert len(ports) == 1
        assert ports[0]["port"] == 25565
        assert ports[0]["protocol"] == "both"
        assert ports[0]["is_main"] is True

    def test_get_all_ports_with_tcp(self):
        """Test get_all_ports when default_port is TCP only"""
        game = GameFactory(default_port="25565/tcp", additional_ports=[])
        ports = game.get_all_ports()
        assert len(ports) == 1
        assert ports[0]["port"] == 25565
        assert ports[0]["protocol"] == "tcp"
        assert ports[0]["is_main"] is True

    def test_get_all_ports_with_udp(self):
        """Test get_all_ports when default_port is UDP only"""
        game = GameFactory(default_port="25565/udp", additional_ports=[])
        ports = game.get_all_ports()
        assert len(ports) == 1
        assert ports[0]["port"] == 25565
        assert ports[0]["protocol"] == "udp"
        assert ports[0]["is_main"] is True

    def test_get_all_ports_with_additional_ports(self):
        """Test get_all_ports with additional ports"""
        game = GameFactory(
            default_port="25565/tcp",
            additional_ports=[
                {"port": 8080, "protocol": "tcp", "description": "Web"},
                {"port": 27015, "protocol": "udp", "description": "Query"},
            ],
        )
        ports = game.get_all_ports()
        assert len(ports) == 3
        assert ports[0]["port"] == 25565
        assert ports[0]["protocol"] == "tcp"
        assert ports[0]["is_main"] is True
        assert ports[1]["port"] == 8080
        assert ports[1]["protocol"] == "tcp"
        assert ports[1]["is_main"] is False
        assert ports[2]["port"] == 27015
        assert ports[2]["protocol"] == "udp"
        assert ports[2]["is_main"] is False
