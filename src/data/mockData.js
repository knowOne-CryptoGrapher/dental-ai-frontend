export const mockStats = {
  today_appointments: 8,
  total_patients: 156,
  total_calls: 342,
  scheduled_appointments: 24
};

export const mockPatients = [
  {
    id: '1', file_number: 'DP-20250715-0001', name: 'Sarah Johnson',
    date_of_birth: '1988-03-15', phone: '+1-555-0101', email: 'sarah.j@email.com',
    emergency_contact_name: 'Mike Johnson', emergency_contact_phone: '+1-555-0102',
    emergency_contact_relationship: 'Spouse', preferred_contact: 'phone',
    consent_given: true, consent_date: '2025-06-01', consent_method: 'digital',
    notes: 'Prefers morning appointments', created_at: '2025-06-01T10:00:00Z'
  },
  {
    id: '2', file_number: 'DP-20250715-0002', name: 'James Wilson',
    date_of_birth: '1975-07-22', phone: '+1-555-0103', email: 'james.w@email.com',
    emergency_contact_name: 'Lisa Wilson', emergency_contact_phone: '+1-555-0104',
    emergency_contact_relationship: 'Spouse', preferred_contact: 'email',
    consent_given: true, consent_date: '2025-05-15', consent_method: 'written',
    notes: 'Allergic to penicillin', created_at: '2025-05-15T14:30:00Z'
  },
  {
    id: '3', file_number: 'DP-20250715-0003', name: 'Emily Chen',
    date_of_birth: '1992-11-08', phone: '+1-555-0105', email: 'emily.c@email.com',
    emergency_contact_name: 'David Chen', emergency_contact_phone: '+1-555-0106',
    emergency_contact_relationship: 'Father', preferred_contact: 'sms',
    consent_given: false, consent_date: null, consent_method: null,
    notes: '', created_at: '2025-07-10T09:15:00Z'
  },
  {
    id: '4', file_number: 'DP-20250715-0004', name: 'Robert Martinez',
    date_of_birth: '1965-01-30', phone: '+1-555-0107', email: 'r.martinez@email.com',
    emergency_contact_name: 'Maria Martinez', emergency_contact_phone: '+1-555-0108',
    emergency_contact_relationship: 'Wife', preferred_contact: 'phone',
    consent_given: true, consent_date: '2025-04-20', consent_method: 'verbal',
    notes: 'Has dental anxiety, needs extra time', created_at: '2025-04-20T11:00:00Z'
  },
  {
    id: '5', file_number: 'DP-20250715-0005', name: 'Amanda Davis',
    date_of_birth: '2000-09-12', phone: '+1-555-0109', email: 'amanda.d@email.com',
    emergency_contact_name: 'Tom Davis', emergency_contact_phone: '+1-555-0110',
    emergency_contact_relationship: 'Brother', preferred_contact: 'email',
    consent_given: true, consent_date: '2025-07-01', consent_method: 'digital',
    notes: 'New patient, referred by Dr. Smith', created_at: '2025-07-01T16:45:00Z'
  }
];

export const mockAppointments = [
  {
    id: 'a1', patient_id: '1', patient_name: 'Sarah Johnson', patient_phone: '+1-555-0101',
    appointment_date: '2025-07-16', appointment_time: '9:00 AM', service_type: 'Cleaning',
    duration_minutes: 60, status: 'scheduled', is_emergency: false,
    notes: 'Regular 6-month cleaning', created_at: '2025-07-10T10:00:00Z'
  },
  {
    id: 'a2', patient_id: '2', patient_name: 'James Wilson', patient_phone: '+1-555-0103',
    appointment_date: '2025-07-16', appointment_time: '10:30 AM', service_type: 'Root Canal',
    duration_minutes: 90, status: 'scheduled', is_emergency: false,
    notes: 'Follow-up from last visit', created_at: '2025-07-08T14:00:00Z'
  },
  {
    id: 'a3', patient_id: '3', patient_name: 'Emily Chen', patient_phone: '+1-555-0105',
    appointment_date: '2025-07-16', appointment_time: '2:00 PM', service_type: 'Emergency',
    duration_minutes: 45, status: 'pending_verification', is_emergency: true,
    notes: 'Severe toothache - EMERGENCY', created_at: '2025-07-15T22:00:00Z'
  },
  {
    id: 'a4', patient_id: '4', patient_name: 'Robert Martinez', patient_phone: '+1-555-0107',
    appointment_date: '2025-07-17', appointment_time: '11:00 AM', service_type: 'Checkup',
    duration_minutes: 30, status: 'pending_verification', is_emergency: false,
    notes: 'Annual checkup', created_at: '2025-07-14T09:00:00Z'
  },
  {
    id: 'a5', patient_id: '5', patient_name: 'Amanda Davis', patient_phone: '+1-555-0109',
    appointment_date: '2025-07-18', appointment_time: '3:30 PM', service_type: 'Consultation',
    duration_minutes: 45, status: 'scheduled', is_emergency: false,
    notes: 'First visit consultation', created_at: '2025-07-12T16:00:00Z'
  }
];

export const mockCallLogs = [
  {
    id: 'c1', call_id: 'retell_001', patient_name: 'Sarah Johnson', patient_phone: '+1-555-0101',
    transcript: 'AI: Thank you for calling Bright Smile Dental. How may I help you?\nCaller: Hi, I\'d like to schedule a cleaning appointment.\nAI: I\'d be happy to help with that. May I have your name?\nCaller: Sarah Johnson.\nAI: Thank you, Sarah. When would you prefer your appointment?\nCaller: Next Wednesday morning if possible.\nAI: Let me check... We have 9:00 AM available on Wednesday. Would that work?\nCaller: Perfect!\nAI: Great! I\'ve scheduled your cleaning for Wednesday at 9:00 AM.',
    duration: 145, status: 'completed', handled_by: 'ai', call_type: 'retell_ai',
    call_summary: { patient_name: 'Sarah Johnson', reason: 'Schedule cleaning', appointment_time: '9:00 AM', notes: 'Regular cleaning' },
    action_taken: 'Schedule appointment', timestamp: '2025-07-15T09:30:00Z',
    start_time: '2025-07-15T09:27:35Z', end_time: '2025-07-15T09:30:00Z'
  },
  {
    id: 'c2', call_id: 'retell_002', patient_name: 'Emily Chen', patient_phone: '+1-555-0105',
    transcript: 'AI: Thank you for calling Bright Smile Dental. How may I help you?\nCaller: I have a really bad toothache and need to see someone urgently.\nAI: I\'m sorry to hear that. This sounds like it could be an emergency. Can I get your name?\nCaller: Emily Chen.\nAI: Emily, I\'m flagging this as urgent. We\'ll get you in as soon as possible. Can you come in tomorrow at 2:00 PM?\nCaller: Yes, please!\nAI: Done. Please come in tomorrow at 2:00 PM for an emergency visit.',
    duration: 98, status: 'completed', handled_by: 'ai', call_type: 'retell_ai',
    call_summary: { patient_name: 'Emily Chen', reason: 'Emergency - severe toothache', appointment_time: '2:00 PM', notes: 'Urgent care needed' },
    action_taken: 'Emergency appointment', timestamp: '2025-07-15T22:15:00Z',
    start_time: '2025-07-15T22:13:22Z', end_time: '2025-07-15T22:15:00Z'
  },
  {
    id: 'c3', call_id: 'retell_003', patient_name: 'Robert Martinez', patient_phone: '+1-555-0107',
    transcript: 'AI: Thank you for calling Bright Smile Dental. How may I help you?\nCaller: I need to book my annual checkup.\nAI: Of course! May I have your name?\nCaller: Robert Martinez.\nAI: Thank you, Robert. I have Thursday at 11:00 AM available. Does that work for you?\nCaller: That works great, thank you.\nAI: Wonderful! Your checkup is confirmed for Thursday at 11:00 AM.',
    duration: 82, status: 'completed', handled_by: 'ai', call_type: 'retell_ai',
    call_summary: { patient_name: 'Robert Martinez', reason: 'Annual checkup', appointment_time: '11:00 AM', notes: '' },
    action_taken: 'Schedule appointment', timestamp: '2025-07-14T10:05:00Z',
    start_time: '2025-07-14T10:03:38Z', end_time: '2025-07-14T10:05:00Z'
  },
  {
    id: 'c4', call_id: 'retell_004', patient_name: null, patient_phone: '+1-555-0200',
    transcript: 'AI: Thank you for calling Bright Smile Dental. How may I help you?\nCaller: What are your office hours?\nAI: Our office is open Monday through Friday from 8:00 AM to 6:00 PM, and Saturday from 9:00 AM to 2:00 PM.\nCaller: Do you accept Delta Dental insurance?\nAI: Yes, we accept most major insurance providers including Delta Dental. Would you like to schedule an appointment?\nCaller: Not right now, thank you.\nAI: No problem! Feel free to call back when you\'re ready. Have a great day!',
    duration: 65, status: 'completed', handled_by: 'ai', call_type: 'retell_ai',
    call_summary: { patient_name: null, reason: 'General inquiry', appointment_time: null, notes: 'Asked about hours and insurance' },
    action_taken: 'inquiry', timestamp: '2025-07-13T15:20:00Z',
    start_time: '2025-07-13T15:19:05Z', end_time: '2025-07-13T15:20:10Z'
  }
];

export const mockNotifications = [
  {
    id: 'n1', type: 'appointment_pending', title: 'New Appointment Needs Verification',
    message: 'Emily Chen scheduled an Emergency for 2025-07-16 at 2:00 PM',
    appointment_id: 'a3', patient_id: '3', patient_name: 'Emily Chen',
    status: 'unread', created_at: '2025-07-15T22:15:00Z',
    metadata: { phone: '+1-555-0105', service: 'Emergency', date: '2025-07-16', time: '2:00 PM', is_emergency: true }
  },
  {
    id: 'n2', type: 'appointment_pending', title: 'New Appointment Needs Verification',
    message: 'Robert Martinez scheduled a Checkup for 2025-07-17 at 11:00 AM',
    appointment_id: 'a4', patient_id: '4', patient_name: 'Robert Martinez',
    status: 'unread', created_at: '2025-07-14T10:05:00Z',
    metadata: { phone: '+1-555-0107', service: 'Checkup', date: '2025-07-17', time: '11:00 AM', is_emergency: false }
  }
];

export const mockAnalytics = {
  metrics: {
    call_volume: { total_calls: 342, calls_answered: 318, calls_missed: 24, emergency_calls: 12 },
    appointments: { total_requested: 186, pending: 8, confirmed: 178 },
    consent: { total_intakes: 156, consent_given: 148, consent_rate: 94.9 },
    duplicates: { duplicates_prevented: 23 },
    emergency: { emergency_routed: 12 }
  },
  trends: {}
};
