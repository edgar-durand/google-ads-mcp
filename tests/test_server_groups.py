"""Tests for main.py server-group / individual-server selection."""

import sys
from unittest.mock import patch

# main.py parses CLI args at import time; pytest's own argv would abort it.
with patch.object(sys, "argv", ["main.py"]):
    import main


def prefixes(servers: set[tuple[str, object]]) -> set[str]:
    return {prefix for prefix, _ in servers}


def test_groups_only() -> None:
    """A group name mounts exactly that group's servers."""
    result = prefixes(main.get_servers_to_mount("core"))
    assert result == {prefix for prefix, _ in main.SERVER_GROUPS["core"]}


def test_multiple_groups_union() -> None:
    """Comma-separated groups are unioned."""
    result = prefixes(main.get_servers_to_mount("core,planning"))
    expected = {prefix for prefix, _ in main.SERVER_GROUPS["core"]} | {
        prefix for prefix, _ in main.SERVER_GROUPS["planning"]
    }
    assert result == expected


def test_all_mounts_everything() -> None:
    """ "all" mounts every server in every group."""
    result = prefixes(main.get_servers_to_mount("all"))
    expected = {
        prefix for servers in main.SERVER_GROUPS.values() for prefix, _ in servers
    }
    assert result == expected


def test_individual_servers_added_on_top_of_groups() -> None:
    """--servers adds a single server without pulling in its whole group."""
    result = prefixes(main.get_servers_to_mount("core", "keyword_plan_idea"))
    core = {prefix for prefix, _ in main.SERVER_GROUPS["core"]}
    assert result == core | {"keyword_plan_idea"}
    # the rest of the planning group must NOT come along
    assert "reach_plan" not in result
    assert "keyword_plan" not in result


def test_unknown_names_are_ignored() -> None:
    """Unknown groups/prefixes are warned about, not fatal."""
    result = prefixes(main.get_servers_to_mount("core,nope", "also_nope"))
    assert result == {prefix for prefix, _ in main.SERVER_GROUPS["core"]}


def test_servers_only_without_groups() -> None:
    """--servers alone mounts just those servers."""
    result = prefixes(main.get_servers_to_mount("", "keyword_plan_idea,geo_target"))
    assert result == {"keyword_plan_idea", "geo_target"}
