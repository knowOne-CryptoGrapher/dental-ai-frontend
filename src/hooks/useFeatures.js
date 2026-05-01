import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const ALL_FEATURES = {
  voice_ai_calls: true, appointments: true, patients: true, call_logs: true,
  calendar: true, analytics: true, insurance: true, audit_log: true,
  multi_location: true, custom_voice: true, custom_routing_rules: true,
  knowledge_base: true, sip_telephony: true,
};

/**
 * useFeatures — practice-portal hook that returns the current plan's
 * feature flags + limits. While loading, returns ALL features as
 * `true` so we don't flash "upgrade" prompts on first paint.
 *
 *   const { features, plan, billingStatus, loaded } = useFeatures();
 *   if (!features.analytics) return <UpgradePrompt feature="analytics" />;
 */
export function useFeatures() {
  const { axiosAuth, user } = useAuth();
  const [data, setData] = useState({
    plan_id: 'basic', plan_name: 'Basic',
    billing_status: 'active',
    features: ALL_FEATURES,
    limits: {},
    loaded: false,
  });

  useEffect(() => {
    if (!user || !user.practice_id) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axiosAuth().get('/billing/features');
        if (!cancelled) setData({ ...r.data, loaded: true });
      } catch {
        // Fall back to all-on so the user isn't locked out by a transient API hiccup
        if (!cancelled) setData(d => ({ ...d, loaded: true }));
      }
    })();
    return () => { cancelled = true; };
  }, [axiosAuth, user]);

  return {
    ...data,
    has: (feature) => Boolean(data.features?.[feature]),
  };
}
