import pytest
from flask import Flask
from ui.app import create_app
from sqlalchemy import create_engine
from flask_jwt_extended import create_access_token

@pytest.fixture
def app():
    # Set up an in-memory SQLite database for testing
    engine = create_engine('sqlite:///:memory:')
    app = create_app(engine)
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def access_token():
    # Generate a token for test cases that require authentication
    return create_access_token(identity='test_user')

def test_login_success(client):
    response = client.post('/login', json={
        'username': 'emperor',
        'password': 'fugazi'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data

def test_login_failure(client):
    response = client.post('/login', json={
        'username': 'wrong_user',
        'password': 'wrong_password'
    })
    assert response.status_code == 401
    data = response.get_json()
    assert data['msg'] == 'Bad username or password'

def skip_test_delete_strategy(client, access_token):
    # Create a dummy strategy in the database for testing
    client.post('/create_strategy', json={
        'broker': 'test_broker',
        'strategy_name': 'test_strategy'
    }, headers={
        'Authorization': f'Bearer {access_token}'
    })
    # Test deleting the strategy
    response = client.post('/delete_strategy', json={
        'broker': 'test_broker',
        'strategy_name': 'test_strategy'
    }, headers={
        'Authorization': f'Bearer {access_token}'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

def skip_test_get_brokers_strategies(client, access_token):
    response = client.get('/get_brokers_strategies', headers={
        'Authorization': f'Bearer {access_token}'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)  # Expecting a list of brokers and strategies
