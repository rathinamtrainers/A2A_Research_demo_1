"""
Tests for orchestrator_agent/tools.py — list_available_agents and get_agent_status.

Reference: F12 — Function Tools; F9 — Agent-to-Agent Routing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


class TestListAvailableAgents:
    """Tests for list_available_agents()."""

    def test_returns_exactly_five_agents(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        assert len(result["agents"]) == 5

    def test_result_has_agents_key(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        assert "agents" in result

    def test_contains_all_expected_agent_names(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        names = {a["name"] for a in result["agents"]}
        expected = {"weather_agent", "research_agent", "code_agent", "data_agent", "async_agent"}
        assert names == expected

    def test_each_agent_has_name_description_url(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        for agent in result["agents"]:
            assert "name" in agent, f"Agent missing 'name': {agent}"
            assert "description" in agent, f"Agent missing 'description': {agent}"
            assert "url" in agent, f"Agent missing 'url': {agent}"

    def test_all_urls_start_with_http(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        for agent in result["agents"]:
            assert agent["url"].startswith("http"), (
                f"URL does not start with http: {agent['url']}"
            )

    def test_descriptions_are_non_empty(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        for agent in result["agents"]:
            assert len(agent["description"]) > 0

    def test_urls_come_from_settings(self, monkeypatch):
        """Agent URLs should reflect the settings singleton values."""
        import orchestrator_agent.tools as tools_mod
        monkeypatch.setattr(tools_mod.settings, "WEATHER_AGENT_URL", "http://custom-weather:9001")
        result = tools_mod.list_available_agents()
        weather = next(a for a in result["agents"] if a["name"] == "weather_agent")
        assert weather["url"] == "http://custom-weather:9001"

    def test_weather_agent_description_mentions_weather(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        weather = next(a for a in result["agents"] if a["name"] == "weather_agent")
        assert "weather" in weather["description"].lower()

    def test_code_agent_description_mentions_code_or_execution(self):
        from orchestrator_agent.tools import list_available_agents
        result = list_available_agents()
        code = next(a for a in result["agents"] if a["name"] == "code_agent")
        assert any(kw in code["description"].lower() for kw in ["code", "execution", "python"])


class TestGetAgentStatus:
    """Tests for get_agent_status() with mocked HTTP calls."""

    def test_unknown_agent_returns_not_reachable(self):
        from orchestrator_agent.tools import get_agent_status
        result = get_agent_status("totally_unknown_agent")
        assert result["reachable"] is False

    def test_unknown_agent_returns_error_message(self):
        from orchestrator_agent.tools import get_agent_status
        result = get_agent_status("fake_agent_xyz")
        assert "error" in result
        assert "Unknown agent" in result["error"]

    def test_unknown_agent_lists_valid_names_in_error(self):
        from orchestrator_agent.tools import get_agent_status
        result = get_agent_status("bogus")
        assert "weather_agent" in result["error"]

    def test_unknown_agent_url_is_none(self):
        from orchestrator_agent.tools import get_agent_status
        result = get_agent_status("not_a_real_agent")
        assert result["url"] is None

    def test_returns_agent_name_in_result(self):
        from orchestrator_agent.tools import get_agent_status
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.side_effect = (
                httpx.ConnectError("refused")
            )
            result = get_agent_status("weather_agent")
        assert result["agent_name"] == "weather_agent"

    def test_reachable_agent_returns_true(self):
        from orchestrator_agent.tools import get_agent_status
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp
            result = get_agent_status("weather_agent")
        assert result["reachable"] is True

    def test_reachable_agent_includes_http_status(self):
        from orchestrator_agent.tools import get_agent_status
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp
            result = get_agent_status("research_agent")
        assert result["http_status"] == 200

    def test_non_200_response_returns_not_reachable(self):
        from orchestrator_agent.tools import get_agent_status
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp
            result = get_agent_status("code_agent")
        assert result["reachable"] is False
        assert result["http_status"] == 503

    def test_404_response_returns_not_reachable(self):
        from orchestrator_agent.tools import get_agent_status
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp
            result = get_agent_status("data_agent")
        assert result["reachable"] is False

    def test_network_error_returns_not_reachable(self):
        from orchestrator_agent.tools import get_agent_status
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.side_effect = (
                httpx.ConnectError("Connection refused")
            )
            result = get_agent_status("weather_agent")
        assert result["reachable"] is False

    def test_network_error_includes_error_message(self):
        from orchestrator_agent.tools import get_agent_status
        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value.get.side_effect = (
                httpx.RequestError("Timeout")
            )
            result = get_agent_status("async_agent")
        assert "error" in result

    def test_probes_well_known_agent_json_endpoint(self):
        """get_agent_status must probe /.well-known/agent.json specifically."""
        from orchestrator_agent.tools import get_agent_status
        mock_resp = MagicMock(status_code=200)
        with patch("httpx.Client") as mock_client_class:
            mock_get = mock_client_class.return_value.__enter__.return_value.get
            mock_get.return_value = mock_resp
            get_agent_status("weather_agent")
            called_url = mock_get.call_args[0][0]
        assert "/.well-known/agent.json" in called_url

    def test_all_valid_agent_names_are_recognised(self):
        """No valid agent name should return 'Unknown agent'."""
        from orchestrator_agent.tools import get_agent_status
        valid_names = ["weather_agent", "research_agent", "code_agent", "data_agent", "async_agent"]
        for name in valid_names:
            with patch("httpx.Client") as mock_client_class:
                mock_client_class.return_value.__enter__.return_value.get.side_effect = (
                    httpx.ConnectError("refused")
                )
                result = get_agent_status(name)
            assert "Unknown agent" not in result.get("error", ""), (
                f"'{name}' should be a recognised agent name"
            )
