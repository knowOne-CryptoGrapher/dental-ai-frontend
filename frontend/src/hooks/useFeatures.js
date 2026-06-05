import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

// All flags start false so gated UI never flashes open before the API resolves.
// On successful fetch these are overwritten by the real plan values from the server.
// On error they stay false (fail closed).
const NO_FEATURES = {
  voice_ai_calls: false, appointments: false, patients: false, call_logs: false,
  calendar: false, analytics: false, insurance: false, audit_log: false,
  multi_location: false, custom_voice: false, custom_routing_rules: false,
  knowledge_base: false, sip_telephony: false,
};

/**
 * useFeatures — practice-portal hook that returns the current plan's
 * feature flags + limits.
 *
 *   const { features, plan, billingStatus, loaded, featuresLoading } = useFeatures();
 *   if (featuresLoading) return <Skeleton />;
 *   if (!features.analytics) return <UpgradePrompt feature="analytics" />;
 *
 * featuresLoading is true until /billing/features resolves (success or error).
 * On error, all feature flags remain false (fail closed, not fail open).
 */
export function useFeatures() {
  const { axiosAuth, user } = useAuth();
  const [data, setData] = useState({
    plan_id: 'basic', plan_name: 'Basic',
    billing_status: 'active',
    features: NO_FEATURES,
    limits: {},
    loaded: false,
    featuresLoading: true,
  });

  useEffect(() => {
    if (!user || !user.practice_id) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axiosAuth().get('/billing/features');
        if (!cancelled) setData({ ...r.data, loaded: true, featuresLoading: false });
      } catch {
        // API error — keep all flags false so gated features stay hidden
        if (!cancelled) setData(d => ({ ...d, loaded: true, featuresLoading: false }));
      }
    })();
    return () => { cancelled = true; };
  }, [axiosAuth, user]);

  return {
    ...data,
    has: (feature) => Boolean(data.features?.[feature]),
  };
}
