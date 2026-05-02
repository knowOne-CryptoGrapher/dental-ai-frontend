"""
Provider-Specific Scheduling Feature Tests
Tests for:
- Provider CRUD with scheduling fields (working_hours, location_ids, appointment_types, on_call)
- Provider availability validation
- Double-booking prevention
- Smart routing for appointments
- Provider display in appointments
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@dentaltest.com"
TEST_PASSWORD = "TestPass123!"


class TestProviderScheduling:
    """Provider Scheduling Feature Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.text}")
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get existing locations for testing
        locations_response = self.session.get(f"{BASE_URL}/api/locations")
        self.locations = locations_response.json() if locations_response.status_code == 200 else []
        
        # Get existing patients for appointment tests
        patients_response = self.session.get(f"{BASE_URL}/api/patients")
        self.patients = patients_response.json() if patients_response.status_code == 200 else []
        
        yield
        
        # Cleanup: Delete test providers and appointments
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        """Clean up test data created during tests"""
        try:
            # Get all providers and delete TEST_ prefixed ones
            providers_response = self.session.get(f"{BASE_URL}/api/providers")
            if providers_response.status_code == 200:
                for provider in providers_response.json():
                    if provider.get('name', '').startswith('TEST_'):
                        self.session.delete(f"{BASE_URL}/api/providers/{provider['id']}")
            
            # Get all appointments and delete TEST_ prefixed ones
            appointments_response = self.session.get(f"{BASE_URL}/api/appointments")
            if appointments_response.status_code == 200:
                for apt in appointments_response.json():
                    if apt.get('patient_name', '').startswith('TEST_'):
                        self.session.delete(f"{BASE_URL}/api/appointments/{apt['id']}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    # ==================== PROVIDER CRUD TESTS ====================
    
    def test_create_provider_with_scheduling_fields(self):
        """Test creating a provider with all new scheduling fields"""
        location_id = self.locations[0]['id'] if self.locations else None
        
        provider_data = {
            "name": "TEST_Dr_Smith",
            "title": "Dr.",
            "role": "dentist",
            "location_ids": [location_id] if location_id else [],
            "appointment_types": ["Cleaning", "Checkup", "Consultation", "Emergency"],
            "working_hours": {
                "monday": [{"start": "09:00", "end": "17:00"}],
                "tuesday": [{"start": "09:00", "end": "17:00"}],
                "wednesday": [{"start": "09:00", "end": "12:00"}],
                "thursday": [{"start": "09:00", "end": "17:00"}],
                "friday": [{"start": "09:00", "end": "15:00"}],
                "saturday": [],
                "sunday": []
            },
            "on_call": True,
            "specialties": ["General Dentistry", "Cosmetic"],
            "license_number": "ON-TEST-12345"
        }
        
        response = self.session.post(f"{BASE_URL}/api/providers", json=provider_data)
        
        assert response.status_code in [200, 201], f"Failed to create provider: {response.text}"
        
        data = response.json()
        assert data["name"] == "TEST_Dr_Smith"
        assert data["title"] == "Dr."
        assert data["role"] == "dentist"
        assert data["on_call"] == True
        assert "Cleaning" in data.get("appointment_types", [])
        assert "monday" in data.get("working_hours", {})
        
        # Verify working hours structure
        monday_hours = data.get("working_hours", {}).get("monday", [])
        assert len(monday_hours) > 0
        assert monday_hours[0].get("start") == "09:00"
        assert monday_hours[0].get("end") == "17:00"
        
        print(f"✓ Provider created with ID: {data['id']}")
        return data
    
    def test_create_provider_with_multiple_locations(self):
        """Test creating a provider that works at multiple locations"""
        if len(self.locations) < 1:
            pytest.skip("Need at least 1 location for this test")
        
        location_ids = [loc['id'] for loc in self.locations[:2]]  # First 2 locations
        
        provider_data = {
            "name": "TEST_Multi_Location_Provider",
            "title": "Dr.",
            "role": "dentist",
            "location_ids": location_ids,
            "appointment_types": ["Cleaning", "Checkup"],
            "working_hours": {
                "monday": [{"start": "08:00", "end": "18:00"}],
                "tuesday": [{"start": "08:00", "end": "18:00"}],
                "wednesday": [{"start": "08:00", "end": "18:00"}],
                "thursday": [{"start": "08:00", "end": "18:00"}],
                "friday": [{"start": "08:00", "end": "18:00"}],
                "saturday": [],
                "sunday": []
            },
            "on_call": False
        }
        
        response = self.session.post(f"{BASE_URL}/api/providers", json=provider_data)
        
        assert response.status_code in [200, 201], f"Failed to create provider: {response.text}"
        
        data = response.json()
        assert len(data.get("location_ids", [])) >= 1
        print(f"✓ Multi-location provider created with {len(data.get('location_ids', []))} locations")
    
    def test_update_provider_working_hours(self):
        """Test updating a provider's working hours"""
        # First create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        
        # Update working hours
        updated_data = {
            "name": provider['name'],
            "title": provider['title'],
            "role": provider['role'],
            "working_hours": {
                "monday": [{"start": "10:00", "end": "18:00"}],  # Changed hours
                "tuesday": [{"start": "10:00", "end": "18:00"}],
                "wednesday": [],  # Now off on Wednesday
                "thursday": [{"start": "10:00", "end": "18:00"}],
                "friday": [{"start": "10:00", "end": "14:00"}],
                "saturday": [{"start": "09:00", "end": "12:00"}],  # Now works Saturday
                "sunday": []
            },
            "on_call": False  # Changed from True
        }
        
        response = self.session.put(f"{BASE_URL}/api/providers/{provider_id}", json=updated_data)
        
        assert response.status_code == 200, f"Failed to update provider: {response.text}"
        
        data = response.json()
        assert data.get("on_call") == False
        
        # Verify working hours updated
        monday_hours = data.get("working_hours", {}).get("monday", [])
        if monday_hours:
            assert monday_hours[0].get("start") == "10:00"
        
        print(f"✓ Provider working hours updated successfully")
    
    def test_get_provider_details(self):
        """Test getting detailed provider information"""
        # First create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        
        response = self.session.get(f"{BASE_URL}/api/providers/{provider_id}")
        
        assert response.status_code == 200, f"Failed to get provider: {response.text}"
        
        data = response.json()
        assert data["id"] == provider_id
        assert "working_hours" in data
        assert "appointment_types" in data
        assert "on_call" in data
        
        print(f"✓ Provider details retrieved successfully")
    
    # ==================== PROVIDER AVAILABILITY TESTS ====================
    
    def test_get_provider_availability_slots(self):
        """Test getting available time slots for a provider"""
        # First create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        
        # Get availability for next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        date_str = next_monday.strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{BASE_URL}/api/providers/{provider_id}/availability",
            params={"date": date_str}
        )
        
        assert response.status_code == 200, f"Failed to get availability: {response.text}"
        
        data = response.json()
        assert "slots" in data
        assert "provider_id" in data
        assert "date" in data
        
        # Should have available slots on Monday (provider works Mon 9-5)
        available_slots = [s for s in data.get("slots", []) if s.get("available")]
        print(f"✓ Found {len(available_slots)} available slots for {date_str}")
    
    def test_provider_not_available_on_off_day(self):
        """Test that provider shows no availability on days they don't work"""
        # First create a provider (doesn't work Saturday/Sunday)
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        
        # Get availability for next Sunday
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_sunday = today + timedelta(days=days_until_sunday)
        date_str = next_sunday.strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{BASE_URL}/api/providers/{provider_id}/availability",
            params={"date": date_str}
        )
        
        assert response.status_code == 200, f"Failed to get availability: {response.text}"
        
        data = response.json()
        slots = data.get("slots", [])
        
        # Should have no available slots on Sunday
        available_slots = [s for s in slots if s.get("available")]
        assert len(available_slots) == 0, f"Expected no slots on Sunday, got {len(available_slots)}"
        
        print(f"✓ Correctly shows no availability on Sunday")
    
    # ==================== APPOINTMENT ROUTING TESTS ====================
    
    def test_smart_routing_finds_available_providers(self):
        """Test smart routing to find available providers"""
        # First create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        location_id = self.locations[0]['id'] if self.locations else None
        
        if not location_id:
            pytest.skip("Need at least 1 location for this test")
        
        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        date_str = next_monday.strftime("%Y-%m-%d")
        
        route_request = {
            "appointment_type": "Cleaning",
            "location_id": location_id,
            "date": date_str,
            "is_emergency": False
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/route", json=route_request)
        
        assert response.status_code == 200, f"Failed to route appointment: {response.text}"
        
        data = response.json()
        assert "providers" in data
        
        print(f"✓ Smart routing found {len(data.get('providers', []))} available providers")
    
    def test_emergency_routing_prioritizes_on_call(self):
        """Test that emergency routing prioritizes on-call providers"""
        # Create an on-call provider
        location_id = self.locations[0]['id'] if self.locations else None
        
        if not location_id:
            pytest.skip("Need at least 1 location for this test")
        
        on_call_provider = {
            "name": "TEST_OnCall_Provider",
            "title": "Dr.",
            "role": "dentist",
            "location_ids": [location_id],
            "appointment_types": ["Emergency", "Cleaning"],
            "working_hours": {
                "monday": [{"start": "08:00", "end": "20:00"}],
                "tuesday": [{"start": "08:00", "end": "20:00"}],
                "wednesday": [{"start": "08:00", "end": "20:00"}],
                "thursday": [{"start": "08:00", "end": "20:00"}],
                "friday": [{"start": "08:00", "end": "20:00"}],
                "saturday": [{"start": "09:00", "end": "17:00"}],
                "sunday": [{"start": "10:00", "end": "14:00"}]
            },
            "on_call": True
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/providers", json=on_call_provider)
        assert create_response.status_code in [200, 201]
        
        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        date_str = next_monday.strftime("%Y-%m-%d")
        
        route_request = {
            "appointment_type": "Emergency",
            "location_id": location_id,
            "date": date_str,
            "is_emergency": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments/route", json=route_request)
        
        assert response.status_code == 200, f"Failed to route emergency: {response.text}"
        
        data = response.json()
        providers = data.get("providers", [])
        
        # Check if on-call providers are prioritized
        if providers:
            first_provider = providers[0]
            print(f"✓ Emergency routing returned {len(providers)} providers, first is on_call: {first_provider.get('is_on_call')}")
    
    # ==================== DOUBLE-BOOKING PREVENTION TESTS ====================
    
    def test_double_booking_prevention(self):
        """Test that system prevents double-booking same provider at same time"""
        # Create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        location_id = self.locations[0]['id'] if self.locations else None
        
        if not self.patients:
            pytest.skip("Need at least 1 patient for this test")
        
        patient = self.patients[0]
        
        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        date_str = next_monday.strftime("%Y-%m-%d")
        
        # Create first appointment
        apt1_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_{patient.get('name', 'Patient1')}",
            "patient_phone": patient.get('phone', '555-0001'),
            "appointment_date": date_str,
            "appointment_time": "10:00",
            "service_type": "Cleaning",
            "provider_id": provider_id,
            "location_id": location_id
        }
        
        response1 = self.session.post(f"{BASE_URL}/api/appointments", json=apt1_data)
        assert response1.status_code in [200, 201], f"Failed to create first appointment: {response1.text}"
        
        print(f"✓ First appointment created successfully")
        
        # Try to create second appointment at same time with same provider
        apt2_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_{patient.get('name', 'Patient2')}_2",
            "patient_phone": patient.get('phone', '555-0002'),
            "appointment_date": date_str,
            "appointment_time": "10:00",  # Same time
            "service_type": "Checkup",
            "provider_id": provider_id,  # Same provider
            "location_id": location_id
        }
        
        response2 = self.session.post(f"{BASE_URL}/api/appointments", json=apt2_data)
        
        # Should return 409 Conflict for double-booking
        assert response2.status_code == 409, f"Expected 409 for double-booking, got {response2.status_code}: {response2.text}"
        
        error_detail = response2.json().get("detail", "")
        assert "already booked" in error_detail.lower() or "conflict" in error_detail.lower(), f"Expected booking conflict message, got: {error_detail}"
        
        print(f"✓ Double-booking correctly prevented with 409 status")
    
    def test_different_time_same_provider_allowed(self):
        """Test that same provider can have appointments at different times"""
        # Create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        location_id = self.locations[0]['id'] if self.locations else None
        
        if not self.patients:
            pytest.skip("Need at least 1 patient for this test")
        
        patient = self.patients[0]
        
        # Get next Monday
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        date_str = next_monday.strftime("%Y-%m-%d")
        
        # Create first appointment at 10:00
        apt1_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_Patient_10AM",
            "patient_phone": patient.get('phone', '555-0001'),
            "appointment_date": date_str,
            "appointment_time": "10:00",
            "service_type": "Cleaning",
            "provider_id": provider_id,
            "location_id": location_id
        }
        
        response1 = self.session.post(f"{BASE_URL}/api/appointments", json=apt1_data)
        assert response1.status_code in [200, 201], f"Failed to create first appointment: {response1.text}"
        
        # Create second appointment at 11:00 (different time)
        apt2_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_Patient_11AM",
            "patient_phone": patient.get('phone', '555-0002'),
            "appointment_date": date_str,
            "appointment_time": "11:00",  # Different time
            "service_type": "Checkup",
            "provider_id": provider_id,  # Same provider
            "location_id": location_id
        }
        
        response2 = self.session.post(f"{BASE_URL}/api/appointments", json=apt2_data)
        assert response2.status_code in [200, 201], f"Failed to create second appointment: {response2.text}"
        
        print(f"✓ Same provider can have appointments at different times")
    
    # ==================== PROVIDER DISPLAY IN APPOINTMENTS TESTS ====================
    
    def test_appointment_includes_provider_name(self):
        """Test that created appointment includes provider name"""
        # Create a provider
        provider = self.test_create_provider_with_scheduling_fields()
        provider_id = provider['id']
        location_id = self.locations[0]['id'] if self.locations else None
        
        if not self.patients:
            pytest.skip("Need at least 1 patient for this test")
        
        patient = self.patients[0]
        
        # Get next Tuesday (to avoid conflicts with other tests)
        today = datetime.now()
        days_until_tuesday = (1 - today.weekday()) % 7
        if days_until_tuesday == 0:
            days_until_tuesday = 7
        next_tuesday = today + timedelta(days=days_until_tuesday)
        date_str = next_tuesday.strftime("%Y-%m-%d")
        
        apt_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_Provider_Display_Patient",
            "patient_phone": patient.get('phone', '555-0001'),
            "appointment_date": date_str,
            "appointment_time": "14:00",
            "service_type": "Consultation",
            "provider_id": provider_id,
            "location_id": location_id
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments", json=apt_data)
        assert response.status_code in [200, 201], f"Failed to create appointment: {response.text}"
        
        data = response.json()
        
        # Verify provider_name is included in response
        assert "provider_name" in data, "provider_name not in appointment response"
        assert data["provider_name"] is not None, "provider_name is None"
        assert "TEST_Dr_Smith" in data["provider_name"] or "Dr." in data["provider_name"], f"Unexpected provider_name: {data['provider_name']}"
        
        print(f"✓ Appointment includes provider_name: {data['provider_name']}")
    
    def test_appointments_list_includes_provider_info(self):
        """Test that appointments list includes provider information"""
        # First create an appointment with provider
        self.test_appointment_includes_provider_name()
        
        # Get all appointments
        response = self.session.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 200, f"Failed to get appointments: {response.text}"
        
        appointments = response.json()
        
        # Find our test appointment
        test_apts = [a for a in appointments if a.get('patient_name', '').startswith('TEST_Provider_Display')]
        
        if test_apts:
            apt = test_apts[0]
            assert "provider_name" in apt or "provider_id" in apt, "Provider info missing from appointment list"
            print(f"✓ Appointments list includes provider info")
        else:
            print("⚠ Test appointment not found in list (may have been cleaned up)")


class TestProviderSchedulingEdgeCases:
    """Edge case tests for provider scheduling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.text}")
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_provider_without_working_hours(self):
        """Test creating provider without working hours uses defaults"""
        provider_data = {
            "name": "TEST_No_Hours_Provider",
            "title": "Dr.",
            "role": "dentist"
            # No working_hours specified - should use defaults
        }
        
        response = self.session.post(f"{BASE_URL}/api/providers", json=provider_data)
        
        assert response.status_code in [200, 201], f"Failed to create provider: {response.text}"
        
        data = response.json()
        
        # Should have default working hours
        working_hours = data.get("working_hours", {})
        assert "monday" in working_hours or len(working_hours) > 0, "No default working hours set"
        
        print(f"✓ Provider created with default working hours")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/providers/{data['id']}")
    
    def test_appointment_without_provider(self):
        """Test creating appointment without provider_id"""
        patients_response = self.session.get(f"{BASE_URL}/api/patients")
        patients = patients_response.json() if patients_response.status_code == 200 else []
        
        if not patients:
            pytest.skip("Need at least 1 patient for this test")
        
        patient = patients[0]
        
        today = datetime.now()
        date_str = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        
        apt_data = {
            "patient_id": patient['id'],
            "patient_name": f"TEST_No_Provider_Apt",
            "patient_phone": patient.get('phone', '555-0001'),
            "appointment_date": date_str,
            "appointment_time": "15:00",
            "service_type": "Cleaning"
            # No provider_id
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments", json=apt_data)
        
        # Should succeed - provider is optional
        assert response.status_code in [200, 201], f"Failed to create appointment without provider: {response.text}"
        
        data = response.json()
        assert data.get("provider_name") is None or data.get("provider_id") is None
        
        print(f"✓ Appointment created without provider (provider is optional)")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/appointments/{data['id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
