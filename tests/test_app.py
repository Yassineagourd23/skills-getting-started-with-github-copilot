from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src import app as app_module


@pytest.fixture
def client():
    # Create a test client that sends requests to the FastAPI application.
    return TestClient(app_module.app)


@pytest.fixture(autouse=True)
def isolate_activities():
    # Save the shared activity data so each test starts with clean state.
    original_activities = deepcopy(app_module.activities)
    yield
    # Restore any changes made by the test after it finishes.
    app_module.activities.clear()
    app_module.activities.update(original_activities)

def test_root_redirects_to_static_index(client):
    # Verify that the root URL redirects to the application's static page.
    expected_location = "/static/index.html"

    # Disable redirect following so the redirect response can be inspected.
    response = client.get("/", follow_redirects=False)

    # Confirm the temporary redirect and its destination.
    assert response.status_code == 307
    assert response.headers["location"] == expected_location

def test_get_activities_returns_activity_catalog(client):
    # Request the complete activity catalog.
    expected_activity = "Chess Club"

    response = client.get("/activities")

    # Check that the catalog contains the expected activity and capacity.
    assert response.status_code == 200
    assert expected_activity in response.json()
    assert response.json()[expected_activity]["max_participants"] == 12


def test_signup_adds_student_to_activity(client):
    # Prepare a valid activity and student email.
    activity_name = "Basketball Club"
    email = "student@mergington.edu"

    # Sign the student up through the API.
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # Verify the response and confirm the participant was stored.
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Signed up {email} for {activity_name}"
    }
    assert email in app_module.activities[activity_name]["participants"]


def test_signup_rejects_unknown_activity(client):
    # Use an activity name that is not in the catalog.
    activity_name = "Unknown Club"
    email = "student@mergington.edu"

    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # The API should report that the activity does not exist.
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_signup_rejects_duplicate_participant(client):
    # Michael is already registered for Chess Club.
    activity_name = "Chess Club"
    email = "michael@mergington.edu"

    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # Duplicate registrations should be rejected as a bad request.
    assert response.status_code == 400
    assert response.json() == {"detail": "Student is already signed up"}


def test_signup_rejects_full_activity(client):
    # Fill every available participant slot before signing up another student.
    activity_name = "Basketball Club"
    activity = app_module.activities[activity_name]
    activity["participants"] = [
        f"student-{number}@mergington.edu"
        for number in range(activity["max_participants"])
    ]

    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": "student@mergington.edu"},
    )

    # The API should reject signups when capacity has been reached.
    assert response.status_code == 400
    assert response.json() == {"detail": "Activity is full"}


def test_remove_participant_removes_student_from_activity(client):
    # Select a currently registered student to remove.
    activity_name = "Chess Club"
    email = "michael@mergington.edu"

    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )

    # Verify the response and ensure the student is no longer registered.
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Removed {email} from {activity_name}"
    }
    assert email not in app_module.activities[activity_name]["participants"]


def test_remove_participant_rejects_unknown_activity(client):
    # Attempt to remove a student from a nonexistent activity.
    activity_name = "Unknown Club"
    email = "student@mergington.edu"

    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )

    # The API should return a not-found error for the activity.
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_remove_participant_rejects_unregistered_student(client):
    # Attempt to remove a student who is not registered.
    activity_name = "Chess Club"
    email = "student@mergington.edu"

    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )

    # The API should return a not-found error for the student.
    assert response.status_code == 404
    assert response.json() == {"detail": "Student is not signed up"}