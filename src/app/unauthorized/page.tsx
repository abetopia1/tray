export default function UnauthorizedPage() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f5f5f5',
    }}>
      <div style={{
        background: '#fff',
        padding: '2rem',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        textAlign: 'center',
        maxWidth: '400px',
      }}>
        <h1 style={{ margin: '0 0 1rem', fontSize: '1.5rem', color: '#dc2626' }}>
          Access Denied
        </h1>
        <p style={{ margin: 0, color: '#6b7280' }}>
          You do not have the required role to access the admin dashboard.
          Contact your administrator to request access.
        </p>
      </div>
    </div>
  );
}
