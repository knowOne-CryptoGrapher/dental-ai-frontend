import React from 'react';
import { Check, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';

const PLAN_COLS = [
  { id: 'basic',        name: 'Basic',        price: '$399'   },
  { id: 'professional', name: 'Professional', price: '$599'   },
  { id: 'enterprise',   name: 'Enterprise',   price: '$999'   },
  { id: 'elite',        name: 'Elite',        price: '$1,499' },
];

const TABLE_ROWS = [
  { type: 'section', label: 'CORE' },
  { label: 'Voice AI Calls', values: ['250',   '750',    '2,500',  '10,000'] },
  { label: 'Providers',       values: ['5',     '15',     '50',     '200']   },
  { label: 'Locations',       values: ['1',     '5',      '25',     '100']   },
  { label: 'Users',           values: ['5',     '25',     '200',    '1,000'] },
  { type: 'section', label: 'FEATURES' },
  { label: 'Appointments',       values: [true,  true,  true,  true]  },
  { label: 'Patients',           values: [true,  true,  true,  true]  },
  { label: 'Calendar',           values: [true,  true,  true,  true]  },
  { label: 'Audit Logs',         values: [true,  true,  true,  true]  },
  { label: 'Analytics',          values: [false, true,  true,  true]  },
  { label: 'Insurance / CDAnet', values: [false, true,  true,  true]  },
  { label: 'Multi-Location',     values: [false, true,  true,  true]  },
  { label: 'Custom Voice',       values: [false, false, true,  true]  },
  { label: 'Knowledge Base',     values: [false, false, true,  true]  },
  { label: 'Routing Rules',      values: [false, false, true,  true]  },
  { label: 'SIP Telephony',      values: [false, false, 'soon','soon'] },
  { type: 'section', label: 'ELITE EXCLUSIVE' },
  { label: 'Dedicated Support SLA',  values: [false, false, false, true] },
  { label: 'HIPAA / PIPEDA BAA',     values: [false, false, false, true] },
  { label: 'Custom Model Selection', values: [false, false, false, true] },
];

function Cell({ value, isEliteCol }) {
  if (value === true) {
    return (
      <span className="flex justify-center">
        <Check
          className={`w-4 h-4 ${isEliteCol ? 'text-[#b8962f]' : 'text-teal-600'}`}
          aria-label="Included"
        />
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="flex justify-center">
        <X className="w-4 h-4 text-gray-300" aria-label="Not included" />
      </span>
    );
  }
  if (value === 'soon') {
    return (
      <span className="flex justify-center">
        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
          Soon
        </span>
      </span>
    );
  }
  return (
    <span className={`text-sm font-semibold ${isEliteCol ? 'text-[#b8962f]' : 'text-gray-700'}`}>
      {value}
    </span>
  );
}

export default function ComparePlansModal({ isOpen, onClose, currentPlan }) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent
        className="max-w-4xl p-0 gap-0"
        aria-describedby="compare-plans-desc"
      >
        <DialogHeader className="px-6 pt-5 pb-4 border-b border-gray-100">
          <DialogTitle className="text-base font-bold text-gray-900">
            Compare Plans
          </DialogTitle>
          <DialogDescription id="compare-plans-desc" className="text-[13px] text-gray-500 mt-0.5">
            Side-by-side feature comparison across all plans.
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-auto max-h-[65vh]">
          <table className="w-full border-collapse min-w-[600px]">
            <thead className="sticky top-0 z-10 bg-white">
              <tr>
                <th className="px-5 py-3 text-left w-44" />
                {PLAN_COLS.map(plan => {
                  const isCurrent = currentPlan === plan.id;
                  const isElite   = plan.id === 'elite';
                  return (
                    <th
                      key={plan.id}
                      className={`px-4 py-3 text-center min-w-[120px] border-b-2 ${
                        isElite
                          ? 'bg-gradient-to-b from-yellow-50 to-white border-[#D4AF37]'
                          : isCurrent
                          ? 'bg-teal-50/70 border-teal-400'
                          : 'bg-white border-gray-100'
                      }`}
                    >
                      {isCurrent && (
                        <div className="mb-1">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            isElite
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-teal-100 text-teal-700'
                          }`}>
                            Current
                          </span>
                        </div>
                      )}
                      <div className={`text-sm font-bold ${isElite ? 'text-[#D4AF37]' : 'text-gray-900'}`}>
                        {plan.name}
                      </div>
                      <div className={`text-xs mt-0.5 ${isElite ? 'text-[#b8962f]' : 'text-gray-500'}`}>
                        {plan.price}
                        <span className="font-normal text-gray-400">/mo</span>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {TABLE_ROWS.map(row => {
                if (row.type === 'section') {
                  return (
                    <tr key={row.label} className="bg-gray-50/80">
                      <td
                        colSpan={5}
                        className="px-5 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-widest"
                      >
                        {row.label}
                      </td>
                    </tr>
                  );
                }

                return (
                  <tr
                    key={row.label}
                    className="border-t border-gray-100 hover:bg-gray-50/30 transition-colors"
                  >
                    <td className="px-5 py-2.5 text-[13px] text-gray-700">{row.label}</td>
                    {row.values.map((val, colIdx) => {
                      const plan      = PLAN_COLS[colIdx];
                      const isCurrent = currentPlan === plan.id;
                      const isElite   = plan.id === 'elite';
                      return (
                        <td
                          key={plan.id}
                          className={`px-4 py-2.5 text-center ${
                            isElite
                              ? 'bg-yellow-50/20'
                              : isCurrent
                              ? 'bg-teal-50/30'
                              : ''
                          }`}
                        >
                          <Cell value={val} isEliteCol={isElite} />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="px-6 py-3 border-t border-gray-100 bg-gray-50/50">
          <p className="text-[11px] text-gray-400 text-center">
            All plans billed monthly · Cancel anytime · Prices in USD
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
