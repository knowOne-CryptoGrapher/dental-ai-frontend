import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';

/**
 * UpgradeModal — shown when a user clicks a plan-gated nav item.
 *
 * Props:
 *   isOpen       — controlled open state
 *   onClose      — called on dismiss or ESC (Radix Dialog handles ESC natively)
 *   featureName  — human-readable feature label, e.g. "Analytics"
 *   requiredTier — tier name, e.g. "Professional"
 *
 * Accessibility: focus trap and ESC-to-close are handled automatically
 * by @radix-ui/react-dialog via the underlying DialogContent primitive.
 */
export default function UpgradeModal({ isOpen, onClose, featureName, requiredTier }) {
  const navigate = useNavigate();

  const handleUpgrade = () => {
    onClose();
    navigate('/billing');
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" aria-describedby="upgrade-modal-desc">
        <DialogHeader>
          <div className="flex items-center justify-center w-10 h-10 rounded-full bg-teal-50 mb-3">
            <Sparkles className="w-5 h-5 text-teal-600" aria-hidden="true" />
          </div>
          <DialogTitle className="text-base">
            Unlock {featureName}
          </DialogTitle>
          <DialogDescription id="upgrade-modal-desc" className="text-sm text-gray-500 mt-1">
            <strong className="text-gray-900">{featureName}</strong> is available on the{' '}
            <span className="font-semibold text-teal-700">{requiredTier}</span> plan and above.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-teal-100 bg-teal-50/60 px-4 py-3 text-sm text-teal-800">
          Upgrade your subscription to access {featureName} and other premium features included in
          the {requiredTier} plan.
        </div>

        <DialogFooter className="mt-2">
          <Button variant="outline" onClick={onClose}>
            Maybe Later
          </Button>
          <Button
            className="bg-teal-600 hover:bg-teal-700 gap-1.5"
            onClick={handleUpgrade}
          >
            Upgrade Plan
            <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
