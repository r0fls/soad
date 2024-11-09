import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import main  # Replace with the correct import if `main.py` is in a different module
import argparse

@pytest.mark.asyncio
@patch("main.parse_config", side_effect=lambda x: {"key": "value"})
@patch("main.create_api_database_engine", return_value=MagicMock())
@patch("main.create_app", return_value=MagicMock(run=MagicMock()))
async def test_start_api_server(mock_create_app, mock_create_engine, mock_parse_config):
    config_path = "dummy_config.yaml"
    await main.start_api_server(config_path)

    mock_parse_config.assert_called_once_with(config_path)
    mock_create_engine.assert_called_once()
    mock_create_app.assert_called_once()
