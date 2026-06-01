import React from "react";
import { Link } from "react-router-dom";

function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="text-xl font-semibold text-gray-800 mb-3">{title}</h2>
      <div className="text-gray-600 space-y-2 leading-relaxed">{children}</div>
    </section>
  );
}

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="mb-8 pb-6 border-b border-gray-200">
          <Link to="/" className="text-sm text-teal-600 hover:underline mb-4 inline-block">
            ← Back
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Terms &amp; Conditions</h1>
          <p className="text-sm text-gray-500 mt-1">Version 1.0 — Last updated: 2026-06-01</p>
        </div>

        <Section title="1. Acceptable use">
          <ul className="list-disc pl-5 space-y-1">
            <li>Dental AI may only be used by licensed dental practices in Canada</li>
            <li>The service may only be used to manage patients of the subscribing practice</li>
            <li>Users must comply with all applicable provincial dental regulations</li>
          </ul>
        </Section>

        <Section title="2. Prohibited use">
          <ul className="list-disc pl-5 space-y-1">
            <li>Sharing access credentials with other practices</li>
            <li>Using the service to store data belonging to another practice</li>
            <li>Attempting to access data outside your assigned practice scope</li>
            <li>Reverse engineering or reselling the service</li>
          </ul>
        </Section>

        <Section title="3. Payment terms">
          <ul className="list-disc pl-5 space-y-1">
            <li>Subscription fees are billed monthly via Stripe</li>
            <li>Fees are non-refundable except as required by law</li>
            <li>Failure to pay may result in service suspension after 14 days notice</li>
          </ul>
        </Section>

        <Section title="4. Cancellation">
          <ul className="list-disc pl-5 space-y-1">
            <li>Either party may cancel with 30 days written notice</li>
            <li>Upon cancellation, data export is available for 30 days</li>
            <li>After 30 days, data is deleted per the retention policy</li>
          </ul>
        </Section>

        <Section title="5. Liability limitations">
          <ul className="list-disc pl-5 space-y-1">
            <li>Dental AI is a software tool, not a licensed dental provider</li>
            <li>We are not liable for clinical decisions made using the service</li>
            <li>Our liability is limited to fees paid in the preceding 3 months</li>
          </ul>
        </Section>

        <Section title="6. Data ownership">
          <ul className="list-disc pl-5 space-y-1">
            <li>Practices own all patient data entered into the system</li>
            <li>Dental AI does not sell or share patient data</li>
            <li>Aggregated, anonymized usage data may be used to improve the service</li>
          </ul>
        </Section>

        <Section title="7. Service uptime">
          <ul className="list-disc pl-5 space-y-1">
            <li>We target 99.5% uptime excluding scheduled maintenance</li>
            <li>Scheduled maintenance will be announced 24 hours in advance where possible</li>
          </ul>
        </Section>

        <Section title="8. Support expectations">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Email support:{" "}
              <a href="mailto:support@dentalai.ca" className="text-teal-600 hover:underline">
                support@dentalai.ca
              </a>
            </li>
            <li>Response time: within 2 business days</li>
            <li>Critical issues (service unavailable): within 4 hours</li>
          </ul>
        </Section>

        <Section title="9. Governing law">
          <p>
            These terms are governed by the laws of British Columbia and the federal laws of
            Canada applicable therein. Any disputes shall be resolved in the courts of British
            Columbia.
          </p>
        </Section>
      </div>
    </div>
  );
}
