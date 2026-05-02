"""
Test suite for Appointment Cancel functionality
Tests the DELETE /api/appointments/{appointment_id} endpoint
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@dentaltest.com"
TEST_PASSWORD = "TestPass123!"


class TestAppointmentCancel:
    """Tests for appointment cancellation functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token = login_response.json().get("access_token")
        assert token, "No access token received"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.user = login_response.json().get("user")
        
    def _get_or_create_patient(self):
        """Get existing test patient or create one"""
        # Get patients
        patients_response = self.session.get(f"{BASE_URL}/api/patients")
        if patients_response.status_code == 200:
            patients = patients_response.json()
            # Find a test patient
            test_patient = next((p for p in patients if p.get("full_name", "").startswith("TEST_")), None)
            if test_patient:
                return test_patient["id"]
            # Use first patient if available
            if patients:
                return patients[0]["id"]
        
        # Create a test patient
        patient_data = {
            "full_name": f"TEST_CancelPatient_{uuid.uuid4().hex[:8]}",
            "phone": "555-0199",
            "email": f"test_{uuid.uuid4().hex[:8]}@test.com"
        }
        create_response = self.session.post(f"{BASE_URL}/api/patients", json=patient_data)
        if create_response.status_code in [200, 201]:
            return create_response.json()["id"]
        return None
        
    def test_cancel_pending_appointment(self):
        """Test cancelling a pending appointment - should succeed"""
        # Get a patient ID first
        patient_id = self._get_or_create_patient()
        assert patient_id, "Could not get or create a patient for testing"
        
        # Create a test appointment
        appointment_data = {
            "patient_id": patient_id,
            "patient_name": f"TEST_Cancel_{uuid.uuid4().hex[:8]}",
            "patient_phone": "555-0100",
            "appointment_date": "2026-12-01",
            "appointment_time": "10:00",
            "service_type": "Cleaning",
            "notes": "Test appointment for cancel test"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data
        )
        assert create_response.status_code == 200, f"Failed to create appointment: {create_response.text}"
        
        appointment = create_response.json()
        appointment_id = appointment["id"]
        assert appointment["status"] == "pending_verification"
        
        # Now cancel the appointment
        cancel_response = self.session.delete(
            f"{BASE_URL}/api/appointments/{appointment_id}"
        )
        assert cancel_response.status_code == 200, f"Cancel failed: {cancel_response.text}"
        
        cancel_data = cancel_response.json()
        assert cancel_data.get("status") == "success"
        
        # Verify the appointment is now cancelled
        get_response = self.session.get(f"{BASE_URL}/api/appointments")
        assert get_response.status_code == 200
        
        appointments = get_response.json()
        cancelled_apt = next((a for a in appointments if a["id"] == appointment_id), None)
        assert cancelled_apt is not None, "Appointment not found after cancel"
        assert cancelled_apt["status"] == "cancelled", f"Expected 'cancelled', got '{cancelled_apt['status']}'"
        
    def test_cancel_scheduled_appointment(self):
        """Test cancelling a scheduled appointment - should succeed"""
        # Get a patient ID first
        patient_id = self._get_or_create_patient()
        assert patient_id, "Could not get or create a patient for testing"
        
        # Create an appointment
        appointment_data = {
            "patient_id": patient_id,
            "patient_name": f"TEST_CancelScheduled_{uuid.uuid4().hex[:8]}",
            "patient_phone": "555-0101",
            "appointment_date": "2026-12-02",
            "appointment_time": "11:00",
            "service_type": "Checkup"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data
        )
        assert create_response.status_code == 200, f"Failed to create: {create_response.text}"
        
        appointment_id = create_response.json()["id"]
        
        # Verify the appointment (change status to scheduled)
        verify_response = self.session.post(
            f"{BASE_URL}/api/appointments/{appointment_id}/verify",
            json={"verified_by": "test"}
        )
        assert verify_response.status_code == 200
        
        # Now cancel the scheduled appointment
        cancel_response = self.session.delete(
            f"{BASE_URL}/api/appointments/{appointment_id}"
        )
        assert cancel_response.status_code == 200
        
        # Verify status changed to cancelled
        get_response = self.session.get(f"{BASE_URL}/api/appointments")
        appointments = get_response.json()
        cancelled_apt = next((a for a in appointments if a["id"] == appointment_id), None)
        assert cancelled_apt["status"] == "cancelled"
        
    def test_cancel_nonexistent_appointment(self):
        """Test cancelling a non-existent appointment - should return 404"""
        fake_id = str(uuid.uuid4())
        
        cancel_response = self.session.delete(
            f"{BASE_URL}/api/appointments/{fake_id}"
        )
        assert cancel_response.status_code == 404
        
    def test_cancel_without_auth(self):
        """Test cancelling without authentication - should return 401/403"""
        # Create a new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        # Try to cancel any appointment
        cancel_response = no_auth_session.delete(
            f"{BASE_URL}/api/appointments/some-id"
        )
        assert cancel_response.status_code in [401, 403], f"Expected 401/403, got {cancel_response.status_code}"
        
    def test_cancel_already_cancelled_appointment(self):
        """Test cancelling an already cancelled appointment - should still succeed (idempotent)"""
        # Get a patient ID first
        patient_id = self._get_or_create_patient()
        assert patient_id, "Could not get or create a patient for testing"
        
        # Create an appointment
        appointment_data = {
            "patient_id": patient_id,
            "patient_name": f"TEST_DoubleCancelled_{uuid.uuid4().hex[:8]}",
            "patient_phone": "555-0102",
            "appointment_date": "2026-12-03",
            "appointment_time": "12:00",
            "service_type": "Consultation"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data
        )
        assert create_response.status_code == 200, f"Failed to create: {create_response.text}"
        
        appointment_id = create_response.json()["id"]
        
        # Cancel first time
        cancel_response1 = self.session.delete(
            f"{BASE_URL}/api/appointments/{appointment_id}"
        )
        assert cancel_response1.status_code == 200
        
        # Cancel second time - should still work (idempotent)
        cancel_response2 = self.session.delete(
            f"{BASE_URL}/api/appointments/{appointment_id}"
        )
        # Could be 200 (idempotent) or 400 (already cancelled) - both are acceptable
        assert cancel_response2.status_code in [200, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
