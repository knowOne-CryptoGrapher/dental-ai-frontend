import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';

/**
 * Tiny error boundary. Catches runtime errors in any subtree so a single
 * malformed payload can't red-screen the whole app. Falls back to a friendly
 * "this section is unavailable" card with a Retry button (calls the optional
 * onReset callback or just re-renders the children fresh).
 *
 * Usage:
 *   <ErrorBoundary label="Hours tab" onReset={refreshPractice}>
 *     <HoursTab ... />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surface to console so devs/testers see the stack
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary:${this.props.label || 'unnamed'}]`, error, info);
  }

  handleReset = () => {
    const { onReset } = this.props;
    this.setState({ error: null });
    if (typeof onReset === 'function') {
      try { onReset(); } catch { /* ignore */ }
    }
  };

  render() {
    if (this.state.error) {
      return (
        <div
          data-testid={`error-boundary-${(this.props.label || 'unnamed').replace(/\s+/g, '-').toLowerCase()}`}
          className="rounded-lg border border-amber-300 bg-amber-50 p-6 text-center"
        >
          <AlertTriangle className="w-8 h-8 mx-auto text-amber-600 mb-2" />
          <h3 className="text-base font-semibold text-amber-900">
            {this.props.label ? `${this.props.label} couldn't load` : "This section couldn't load"}
          </h3>
          <p className="text-sm text-amber-700 mt-1 mb-4">
            {this.props.message || 'A display error occurred. Try refreshing — your data is safe.'}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={this.handleReset}
            data-testid={`error-boundary-retry-${(this.props.label || 'unnamed').replace(/\s+/g, '-').toLowerCase()}`}
          >
            <RefreshCw className="w-4 h-4 mr-2" /> Retry
          </Button>
          {process.env.NODE_ENV !== 'production' && (
            <pre className="mt-4 text-xs text-left text-amber-800 bg-amber-100 p-2 rounded overflow-auto max-h-32">
              {String(this.state.error?.message || this.state.error)}
            </pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
