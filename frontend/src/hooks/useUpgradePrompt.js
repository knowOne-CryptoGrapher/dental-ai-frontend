import { useState, useCallback } from 'react';
import UpgradeModal from '../components/UpgradeModal';

/**
 * useUpgradePrompt — manages state for the plan upgrade modal.
 *
 * Usage:
 *   const { showUpgradePrompt, UpgradeModalWrapper } = useUpgradePrompt();
 *
 *   // Place once anywhere in the render tree:
 *   {UpgradeModalWrapper}
 *
 *   // To open the modal:
 *   showUpgradePrompt("Analytics", "Professional")
 *
 * UpgradeModalWrapper is a JSX element, not a component function — place it
 * as {UpgradeModalWrapper}, not <UpgradeModalWrapper />.  Returning an element
 * (rather than a component type) keeps the UpgradeModal instance stable across
 * re-renders so Radix Dialog can play its close animation correctly.
 */
export function useUpgradePrompt() {
  const [state, setState] = useState({
    open: false,
    featureName: '',
    requiredTier: '',
  });

  const close = useCallback(
    () => setState(s => ({ ...s, open: false })),
    []
  );

  const showUpgradePrompt = useCallback(
    (featureName, requiredTier) => {
      setState({ open: true, featureName, requiredTier });
    },
    []
  );

  const UpgradeModalWrapper = (
    <UpgradeModal
      isOpen={state.open}
      onClose={close}
      featureName={state.featureName}
      requiredTier={state.requiredTier}
    />
  );

  return { showUpgradePrompt, UpgradeModalWrapper };
}
