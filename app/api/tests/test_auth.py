"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, mock_user_data):
    """Test user registration."""
    response = await client.post("/api/v1/auth/register", json=mock_user_data)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == mock_user_data["email"]
    assert data["full_name"] == mock_user_data["full_name"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, mock_user_data):
    """Test registration with duplicate email fails."""
    # Register first user
    await client.post("/api/v1/auth/register", json=mock_user_data)

    # Try to register with same email
    response = await client.post("/api/v1/auth/register", json=mock_user_data)

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, mock_user_data):
    """Test successful login."""
    # Register user first
    await client.post("/api/v1/auth/register", json=mock_user_data)

    # Login
    login_data = {
        "email": mock_user_data["email"],
        "password": mock_user_data["password"],
    }
    response = await client.post("/api/v1/auth/login", json=login_data)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, mock_user_data):
    """Test login with wrong password fails."""
    # Register user first
    await client.post("/api/v1/auth/register", json=mock_user_data)

    # Login with wrong password
    login_data = {
        "email": mock_user_data["email"],
        "password": "wrongpassword",
    }
    response = await client.post("/api/v1/auth/login", json=login_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, mock_user_data):
    """Test getting current user with valid token."""
    # Register and login
    await client.post("/api/v1/auth/register", json=mock_user_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": mock_user_data["email"],
            "password": mock_user_data["password"],
        },
    )
    token = login_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == mock_user_data["email"]


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, mock_user_data):
    """Test token refresh."""
    # Register and login
    await client.post("/api/v1/auth/register", json=mock_user_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": mock_user_data["email"],
            "password": mock_user_data["password"],
        },
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
