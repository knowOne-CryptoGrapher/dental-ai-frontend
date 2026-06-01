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

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="mb-8 pb-6 border-b border-gray-200">
          <Link to="/" className="text-sm text-teal-600 hover:underline mb-4 inline-block">
            ← Back
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Privacy Policy</h1>
          <p className="text-sm text-gray-500 mt-1">Version 1.0 — Last updated: 2026-06-01</p>
        </div>

        <Section title="1. What data we collect">
          <ul className="list-disc pl-5 space-y-1">
            <li>Practice information (name, address, province, contact details)</li>
            <li>Patient appointment and insurance data entered by clinic staff</li>
            <li>Call recordings and transcripts (when using the AI receptionist)</li>
            <li>Authentication credentials (hashed — never stored in plaintext)</li>
            <li>Usage logs (anonymized)</li>
          </ul>
        </Section>

        <Section title="2. Why we collect it">
          <ul className="list-disc pl-5 space-y-1">
            <li>To provide the AI receptionist and practice management services</li>
            <li>To process insurance claims via CDAnet/iTRANS</li>
            <li>To comply with dental regulatory requirements</li>
          </ul>
        </Section>

        <Section title="3. Where data is stored">
          <p>All patient data is stored in Canada:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>BC / AB / SK / MB clinics: Calgary region (Google Cloud <code className="bg-gray-100 px-1 rounded text-sm">northamerica-west2</code>)</li>
            <li>ON / QC / Atlantic clinics: Montreal region (Google Cloud <code className="bg-gray-100 px-1 rounded text-sm">northamerica-northeast1</code>)</li>
          </ul>
          <p className="mt-2">Data does not leave Canada except as described in cross-border processing below.</p>
        </Section>

        <Section title="4. Cross-border processing disclosure">
          <p>
            Some data is processed by third-party AI providers outside Canada for the purpose
            of generating AI responses. Before being sent, patient names, contact details, and
            health identifiers are replaced with anonymized placeholders. Raw patient data is
            never transmitted to third-party AI providers.
          </p>
        </Section>

        <Section title="5. Vendors used and DPA status">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 font-medium text-gray-700">Vendor</th>
                  <th className="text-left py-2 pr-4 font-medium text-gray-700">Purpose</th>
                  <th className="text-left py-2 font-medium text-gray-700">DPA status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {[
                  ["MongoDB Atlas", "Data storage", "In place"],
                  ["Google Cloud", "Compute and infrastructure", "In place"],
                  ["Stripe", "Billing only, no clinical data", "In place"],
                  ["OpenAI", "AI inference, anonymized prompts only", "In progress"],
                  ["Anthropic", "AI inference, anonymized prompts only", "In progress"],
                  ["Groq", "AI inference, anonymized prompts only", "In progress"],
                  ["Retell", "Voice call handling, call audio and transcripts", "In progress"],
                ].map(([vendor, purpose, status]) => (
                  <tr key={vendor}>
                    <td className="py-2 pr-4 font-medium">{vendor}</td>
                    <td className="py-2 pr-4 text-gray-600">{purpose}</td>
                    <td className={`py-2 ${status === "In place" ? "text-green-600" : "text-amber-600"}`}>{status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="6. Data retention">
          <ul className="list-disc pl-5 space-y-1">
            <li>Patient records: 7 years from last visit (per provincial dental regulations)</li>
            <li>Audit logs: 7 years minimum</li>
            <li>Call transcripts: 90 days, then anonymized</li>
            <li>Usage logs: 90 days</li>
          </ul>
        </Section>

        <Section title="7. Data deletion">
          <ul className="list-disc pl-5 space-y-1">
            <li>Practices may request deletion of their data by contacting support</li>
            <li>Patient data cannot be deleted if retention is required by law</li>
            <li>Deletion requests are processed within 30 days</li>
          </ul>
        </Section>

        <Section title="8. Individual rights (PIPEDA)">
          <ul className="list-disc pl-5 space-y-1">
            <li>You have the right to access personal information we hold about you</li>
            <li>You have the right to correct inaccurate information</li>
            <li>You have the right to request deletion (subject to legal retention requirements)</li>
            <li>You have the right to withdraw consent, subject to legal and contractual restrictions</li>
          </ul>
          <p className="mt-2">
            To exercise these rights, contact:{" "}
            <a href="mailto:privacy@dentalai.ca" className="text-teal-600 hover:underline">
              privacy@dentalai.ca
            </a>
          </p>
        </Section>

        <Section title="9. Contact information">
          <p>
            Privacy Officer:{" "}
            <a href="mailto:privacy@dentalai.ca" className="text-teal-600 hover:underline">
              privacy@dentalai.ca
            </a>
          </p>
          <p className="text-gray-400 text-sm mt-1">Mailing address: [to be completed before launch]</p>
        </Section>
      </div>
    </div>
  );
}
