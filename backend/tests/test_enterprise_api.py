"""
DentalAI Enterprise SaaS API Tests
Tests: Authentication, RBAC, Multi-Tenancy, CRUD operations
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@dentaltest.com"
ADMIN_PASSWORD = "TestPass123!"

# For multi-tenancy testing
SECOND_ADMIN_EMAIL = f"admin2_{uuid.uuid4().hex[:6]}@dentaltest.com"
SECOND_ADMIN_PASSWORD = "TestPass456!"
SECOND_PRACTICE_NAME = "Second Test Practice"


class TestHealthAndBasics:
    """Basic API health checks"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "DentalAI" in data["message"]
        print(f"✓ API root working: {data['message']}")


class TestAuthentication:
    """Authentication flow tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")
    
    def test_get_me_authenticated(self):
        """Test /auth/me with valid token"""
        # First login
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_res.json()["access_token"]
        
        # Get user info
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert "practice_id" in data
        print(f"✓ /auth/me returns correct user data")
    
    def test_get_me_unauthenticated(self):
        """Test /auth/me without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code in [401, 403]
        print("✓ Unauthenticated request correctly rejected")


class TestRBACEnforcement:
    """Role-Based Access Control tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def staff_user(self, admin_token):
        """Create a staff user for RBAC testing"""
        staff_email = f"staff_{uuid.uuid4().hex[:6]}@dentaltest.com"
        response = requests.post(f"{BASE_URL}/api/auth/invite", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": staff_email,
                "full_name": "Test Staff",
                "role": "staff"
            }
        )
        if response.status_code == 200:
            temp_password = response.json()["temporary_password"]
            # Login as staff
            login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": staff_email,
                "password": temp_password
            })
            return {"token": login_res.json()["access_token"], "email": staff_email}
        return None
    
    @pytest.fixture
    def auditor_user(self, admin_token):
        """Create an auditor user for RBAC testing"""
        auditor_email = f"auditor_{uuid.uuid4().hex[:6]}@dentaltest.com"
        response = requests.post(f"{BASE_URL}/api/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": auditor_email,
                "full_name": "Test Auditor",
                "role": "auditor"
            }
        )
        if response.status_code == 200:
            temp_password = response.json()["temporary_password"]
            login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": auditor_email,
                "password": temp_password
            })
            return {"token": login_res.json()["access_token"], "email": auditor_email}
        return None
    
    def test_admin_can_delete_patient(self, admin_token):
        """Admin should be able to delete patients"""
        # First create a patient
        create_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "TEST_DeleteMe Patient",
                "phone": f"555-{uuid.uuid4().hex[:4]}"
            }
        )
        assert create_res.status_code == 200, f"Failed to create patient: {create_res.text}"
        patient_id = create_res.json()["id"]
        
        # Admin deletes patient
        delete_res = requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_res.status_code == 200, f"Admin should be able to delete patient: {delete_res.text}"
        print("✓ Admin can delete patients")
    
    def test_staff_cannot_delete_patient(self, admin_token, staff_user):
        """Staff should NOT be able to delete patients"""
        if not staff_user:
            pytest.skip("Could not create staff user")
        
        # Create a patient as admin
        create_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "TEST_StaffCantDelete Patient",
                "phone": f"555-{uuid.uuid4().hex[:4]}"
            }
        )
        patient_id = create_res.json()["id"]
        
        # Staff tries to delete - should fail with 403
        delete_res = requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {staff_user['token']}"}
        )
        assert delete_res.status_code == 403, f"Staff should NOT be able to delete patients, got {delete_res.status_code}"
        print("✓ Staff correctly denied patient deletion")
        
        # Cleanup - admin deletes
        requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
    
    def test_auditor_can_view_audit_logs(self, auditor_user):
        """Auditor should be able to view audit logs"""
        if not auditor_user:
            pytest.skip("Could not create auditor user")
        
        response = requests.get(f"{BASE_URL}/api/audit-logs",
            headers={"Authorization": f"Bearer {auditor_user['token']}"}
        )
        assert response.status_code == 200, f"Auditor should view audit logs: {response.text}"
        print("✓ Auditor can view audit logs")
    
    def test_staff_cannot_view_audit_logs(self, staff_user):
        """Staff should NOT be able to view audit logs"""
        if not staff_user:
            pytest.skip("Could not create staff user")
        
        response = requests.get(f"{BASE_URL}/api/audit-logs",
            headers={"Authorization": f"Bearer {staff_user['token']}"}
        )
        assert response.status_code == 403, f"Staff should NOT view audit logs, got {response.status_code}"
        print("✓ Staff correctly denied audit log access")
    
    def test_admin_can_modify_settings(self, admin_token):
        """Admin should be able to modify voice settings"""
        response = requests.post(f"{BASE_URL}/api/settings/voice",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"voice_model": "Polly.Matthew"}
        )
        assert response.status_code == 200, f"Admin should modify settings: {response.text}"
        print("✓ Admin can modify settings")
    
    def test_staff_cannot_modify_settings(self, staff_user):
        """Staff should NOT be able to modify settings"""
        if not staff_user:
            pytest.skip("Could not create staff user")
        
        response = requests.post(f"{BASE_URL}/api/settings/voice",
            headers={"Authorization": f"Bearer {staff_user['token']}"},
            json={"voice_model": "Polly.Matthew"}
        )
        assert response.status_code == 403, f"Staff should NOT modify settings, got {response.status_code}"
        print("✓ Staff correctly denied settings modification")


class TestMultiTenancy:
    """Multi-tenant data isolation tests"""
    
    @pytest.fixture
    def practice1_token(self):
        """Get token for first practice (existing admin)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def practice2_data(self):
        """Create second practice and get token"""
        # Register new practice
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": SECOND_ADMIN_EMAIL,
            "password": SECOND_ADMIN_PASSWORD,
            "full_name": "Second Admin",
            "practice_name": SECOND_PRACTICE_NAME
        })
        if response.status_code == 200:
            data = response.json()
            return {
                "token": data["access_token"],
                "practice_id": data["user"]["practice_id"]
            }
        elif response.status_code == 400:
            # Email already exists, try login
            login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": SECOND_ADMIN_EMAIL,
                "password": SECOND_ADMIN_PASSWORD
            })
            if login_res.status_code == 200:
                data = login_res.json()
                return {
                    "token": data["access_token"],
                    "practice_id": data["user"]["practice_id"]
                }
        return None
    
    def test_practice_cannot_see_other_practice_patients(self, practice1_token, practice2_data):
        """Practice 1 should not see Practice 2's patients"""
        if not practice2_data:
            pytest.skip("Could not create second practice")
        
        # Create patient in practice 2
        create_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {practice2_data['token']}"},
            json={
                "name": "TEST_Practice2Only Patient",
                "phone": f"555-{uuid.uuid4().hex[:4]}"
            }
        )
        assert create_res.status_code == 200
        patient_id = create_res.json()["id"]
        
        # Practice 1 tries to get this patient - should fail
        get_res = requests.get(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {practice1_token}"}
        )
        assert get_res.status_code == 404, f"Practice 1 should NOT see Practice 2's patient, got {get_res.status_code}"
        print("✓ Multi-tenant patient isolation working")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {practice2_data['token']}"}
        )
    
    def test_practice_cannot_see_other_practice_appointments(self, practice1_token, practice2_data):
        """Practice 1 should not see Practice 2's appointments"""
        if not practice2_data:
            pytest.skip("Could not create second practice")
        
        # Get practice 1 appointments
        p1_res = requests.get(f"{BASE_URL}/api/appointments",
            headers={"Authorization": f"Bearer {practice1_token}"}
        )
        
        # Get practice 2 appointments
        p2_res = requests.get(f"{BASE_URL}/api/appointments",
            headers={"Authorization": f"Bearer {practice2_data['token']}"}
        )
        
        assert p1_res.status_code == 200
        assert p2_res.status_code == 200
        
        # Verify they don't share data (different practice_ids)
        p1_ids = set(a.get("practice_id") for a in p1_res.json() if a.get("practice_id"))
        p2_ids = set(a.get("practice_id") for a in p2_res.json() if a.get("practice_id"))
        
        # If both have data, they should not overlap
        if p1_ids and p2_ids:
            assert p1_ids.isdisjoint(p2_ids), "Practices should have isolated data"
        print("✓ Multi-tenant appointment isolation working")


class TestLocationsCRUD:
    """Locations CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_locations(self, admin_token):
        """Get all locations"""
        response = requests.get(f"{BASE_URL}/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ Got {len(response.json())} locations")
    
    def test_create_location(self, admin_token):
        """Create a new location"""
        response = requests.post(f"{BASE_URL}/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "TEST_Branch Office",
                "address": "456 Test St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 2H1",
                "phone": "(416) 555-0200",
                "timezone": "America/Toronto"
            }
        )
        assert response.status_code == 200, f"Failed to create location: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Branch Office"
        assert "id" in data
        print(f"✓ Created location: {data['name']}")
        return data["id"]
    
    def test_update_location(self, admin_token):
        """Update a location"""
        # First create
        create_res = requests.post(f"{BASE_URL}/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_ToUpdate Location", "timezone": "America/Toronto"}
        )
        location_id = create_res.json()["id"]
        
        # Update
        update_res = requests.put(f"{BASE_URL}/api/locations/{location_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Updated Location", "timezone": "America/Vancouver"}
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "TEST_Updated Location"
        print("✓ Location updated successfully")
    
    def test_delete_location(self, admin_token):
        """Delete (deactivate) a location"""
        # First create
        create_res = requests.post(f"{BASE_URL}/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_ToDelete Location", "timezone": "America/Toronto"}
        )
        location_id = create_res.json()["id"]
        
        # Delete
        delete_res = requests.delete(f"{BASE_URL}/api/locations/{location_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_res.status_code == 200
        print("✓ Location deleted (deactivated) successfully")


class TestProvidersCRUD:
    """Providers CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_providers(self, admin_token):
        """Get all providers"""
        response = requests.get(f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ Got {len(response.json())} providers")
    
    def test_create_provider(self, admin_token):
        """Create a new provider"""
        response = requests.post(f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "TEST_John Smith",
                "title": "Dr.",
                "specialties": ["General Dentistry", "Orthodontics"],
                "license_number": "ON-TEST-12345"
            }
        )
        assert response.status_code == 200, f"Failed to create provider: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_John Smith"
        print(f"✓ Created provider: {data['title']} {data['name']}")
        return data["id"]
    
    def test_update_provider(self, admin_token):
        """Update a provider"""
        # First create
        create_res = requests.post(f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_ToUpdate Provider", "title": "Dr."}
        )
        provider_id = create_res.json()["id"]
        
        # Update
        update_res = requests.put(f"{BASE_URL}/api/providers/{provider_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Updated Provider", "title": "Hygienist"}
        )
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "Hygienist"
        print("✓ Provider updated successfully")


class TestPatientsCRUD:
    """Patients CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_patients(self, admin_token):
        """Get all patients"""
        response = requests.get(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ Got {len(response.json())} patients")
    
    def test_create_patient(self, admin_token):
        """Create a new patient"""
        unique_phone = f"555-{uuid.uuid4().hex[:4]}"
        response = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "TEST_Jane Doe",
                "phone": unique_phone,
                "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                "date_of_birth": "1990-05-15",
                "preferred_contact": "email"
            }
        )
        assert response.status_code == 200, f"Failed to create patient: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Jane Doe"
        assert "file_number" in data
        print(f"✓ Created patient: {data['name']} (File: {data['file_number']})")
        return data["id"]
    
    def test_update_patient(self, admin_token):
        """Update a patient"""
        # First create
        unique_phone = f"555-{uuid.uuid4().hex[:4]}"
        create_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_ToUpdate Patient", "phone": unique_phone}
        )
        patient_id = create_res.json()["id"]
        
        # Update
        update_res = requests.put(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Updated Patient", "phone": unique_phone, "notes": "Updated notes"}
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "TEST_Updated Patient"
        print("✓ Patient updated successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
    
    def test_duplicate_patient_prevention(self, admin_token):
        """Test duplicate patient detection"""
        unique_phone = f"555-{uuid.uuid4().hex[:4]}"
        
        # Create first patient
        create_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Duplicate Patient", "phone": unique_phone}
        )
        assert create_res.status_code == 200
        patient_id = create_res.json()["id"]
        
        # Try to create duplicate
        dup_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Another Patient", "phone": unique_phone}
        )
        assert dup_res.status_code == 409, f"Should detect duplicate, got {dup_res.status_code}"
        print("✓ Duplicate patient correctly detected")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )


class TestAppointmentsCRUD:
    """Appointments CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def test_patient(self, admin_token):
        """Create a test patient for appointments"""
        unique_phone = f"555-{uuid.uuid4().hex[:4]}"
        response = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Appointment Patient", "phone": unique_phone}
        )
        return response.json()
    
    def test_get_appointments(self, admin_token):
        """Get all appointments"""
        response = requests.get(f"{BASE_URL}/api/appointments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ Got {len(response.json())} appointments")
    
    def test_create_appointment(self, admin_token, test_patient):
        """Create a new appointment"""
        response = requests.post(f"{BASE_URL}/api/appointments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "patient_id": test_patient["id"],
                "patient_name": test_patient["name"],
                "patient_phone": test_patient["phone"],
                "appointment_date": "2025-02-15",
                "appointment_time": "10:00",
                "service_type": "Cleaning",
                "duration_minutes": 60
            }
        )
        assert response.status_code == 200, f"Failed to create appointment: {response.text}"
        data = response.json()
        assert data["status"] == "pending_verification"
        print(f"✓ Created appointment for {data['patient_name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{test_patient['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        return data["id"]
    
    def test_emergency_detection(self, admin_token, test_patient):
        """Test emergency keyword detection"""
        response = requests.post(f"{BASE_URL}/api/appointments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "patient_id": test_patient["id"],
                "patient_name": test_patient["name"],
                "patient_phone": test_patient["phone"],
                "appointment_date": "2025-02-15",
                "appointment_time": "14:00",
                "service_type": "Emergency",
                "notes": "Patient has severe pain and swelling"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_emergency"] == True, "Should detect emergency keywords"
        print("✓ Emergency detection working")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{test_patient['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )


class TestInsuranceMocked:
    """Insurance endpoints (MOCKED ITRANS/CDANet)"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_carriers(self, admin_token):
        """Get list of insurance carriers"""
        response = requests.get(f"{BASE_URL}/api/insurance/carriers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        carriers = response.json()
        assert len(carriers) > 0
        assert any(c["id"] == "sun_life" for c in carriers)
        print(f"✓ Got {len(carriers)} insurance carriers (MOCKED)")
    
    def test_check_eligibility(self, admin_token):
        """Check insurance eligibility (MOCKED)"""
        response = requests.post(f"{BASE_URL}/api/insurance/eligibility",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "carrier": "sun_life",
                "policy_number": "TEST-12345",
                "patient_name": "Test Patient"
            }
        )
        assert response.status_code == 200, f"Eligibility check failed: {response.text}"
        data = response.json()
        assert data["status"] == "eligible"
        assert "coverage" in data
        assert "MOCKED" in data.get("note", "")
        print("✓ Eligibility check working (MOCKED)")
    
    def test_submit_claim(self, admin_token):
        """Submit insurance claim (MOCKED)"""
        # First create a patient
        unique_phone = f"555-{uuid.uuid4().hex[:4]}"
        patient_res = requests.post(f"{BASE_URL}/api/patients",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "TEST_Claim Patient", "phone": unique_phone}
        )
        patient_id = patient_res.json()["id"]
        
        # Submit claim
        response = requests.post(f"{BASE_URL}/api/insurance/submit-claim",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "patient_id": patient_id,
                "carrier": "manulife",
                "policy_number": "TEST-67890",
                "procedures": [
                    {"code": "01101", "description": "Exam", "fee": 75.00},
                    {"code": "11101", "description": "Cleaning", "fee": 150.00}
                ]
            }
        )
        assert response.status_code == 200, f"Claim submission failed: {response.text}"
        data = response.json()
        assert data["status"] == "submitted"
        assert data["total_amount"] == 225.00
        print("✓ Claim submission working (MOCKED)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )


class TestDashboardStats:
    """Dashboard statistics"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_stats(self, admin_token):
        """Get dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_patients" in data
        assert "scheduled_appointments" in data
        assert "locations" in data
        assert "providers" in data
        print(f"✓ Dashboard stats: {data['total_patients']} patients, {data['locations']} locations")
    
    def test_analytics_dashboard(self, admin_token):
        """Get analytics dashboard"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        print("✓ Analytics dashboard working")


class TestAuditLogs:
    """Audit log functionality"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_audit_logs(self, admin_token):
        """Get audit logs"""
        response = requests.get(f"{BASE_URL}/api/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        print(f"✓ Got {len(data['logs'])} audit log entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
