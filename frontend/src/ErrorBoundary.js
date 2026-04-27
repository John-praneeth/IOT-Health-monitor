import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
          color: 'white',
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <h1 style={{ fontSize: '3rem', marginBottom: '1rem' }}>Oops! 🏥</h1>
          <p style={{ fontSize: '1.2rem', color: '#94a3b8', maxWidth: '600px', marginBottom: '2rem' }}>
            A critical component crashed. Our medical system has isolated the error.
            Please try refreshing the page.
          </p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              padding: '12px 24px',
              fontSize: '1rem',
              fontWeight: '600',
              color: 'white',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'background 0.2s'
            }}
          >
            Refresh Dashboard
          </button>
          {process.env.NODE_ENV === 'development' && (
            <pre style={{
              marginTop: '2rem',
              padding: '1rem',
              background: 'rgba(0,0,0,0.3)',
              borderRadius: '8px',
              textAlign: 'left',
              width: '100%',
              maxWidth: '800px',
              overflow: 'auto',
              color: '#f87171',
              fontSize: '0.9rem'
            }}>
              {this.state.error && this.state.error.toString()}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
