from pathlib import Path

import yaml

from real_world_validation.__main__ import EXIT_FAILURES, EXIT_INVALID, EXIT_OK, main

_EXPECTED = {
    "system": "quarkus-super-heroes",
    "upstream_revision": "abc123",
    "scope": {"entities": ["service:rest-fights"], "relation_types": ["CALLS"]},
    "expected": {
        "relations": [
            {
                "id": "qsh-1",
                "type": "CALLS",
                "source": "service:rest-fights",
                "target": "operation:service:rest-heroes:GET:/api/heroes",
            }
        ]
    },
}


def _write(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data))
    return path


def test_main_exits_ok_on_a_clean_match(tmp_path, capsys):
    expected = _write(tmp_path, "expected.yaml", _EXPECTED)
    actual = _write(
        tmp_path,
        "actual.yaml",
        {
            "relations": [
                {
                    "type": "CALLS",
                    "source": "service:rest-fights",
                    "target": "operation:service:rest-heroes:GET:/api/heroes",
                }
            ]
        },
    )

    code = main(["compare", "--expected", str(expected), "--actual", str(actual)])

    assert code == EXIT_OK
    assert "Critical semantic errors:      0" in capsys.readouterr().out


def test_main_exits_failures_on_an_invented_relation(tmp_path, capsys):
    expected = _write(tmp_path, "expected.yaml", _EXPECTED)
    actual = _write(
        tmp_path,
        "actual.yaml",
        {
            "relations": [
                {
                    "type": "CALLS",
                    "source": "service:rest-fights",
                    "target": "operation:service:rest-heroes:GET:/api/heroes",
                },
                {
                    "type": "CALLS",
                    "source": "service:rest-fights",
                    "target": "operation:service:rest-villains:GET:/api/villains",
                },
            ]
        },
    )

    code = main(["compare", "--expected", str(expected), "--actual", str(actual)])

    assert code == EXIT_FAILURES


def test_main_exits_invalid_on_malformed_expected(tmp_path):
    bad = _write(tmp_path, "expected.yaml", {"system": "x"})  # missing required fields
    actual = _write(tmp_path, "actual.yaml", {"relations": []})

    code = main(["compare", "--expected", str(bad), "--actual", str(actual)])

    assert code == EXIT_INVALID
