import KpiCards from './components/KpiCards';
import ActionQueues from './components/ActionQueues';
import GlobalSearch from './components/GlobalSearch';

export default function AdminDashboard() {
  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ margin: '0 0 0.25rem', fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>
          Dashboard
        </h1>
        <p style={{ margin: 0, color: '#6b7280', fontSize: '0.875rem' }}>
          Overview of platform activity and pending actions
        </p>
      </div>

      {/* Global Search */}
      <section style={{ marginBottom: '2rem' }}>
        <GlobalSearch />
      </section>

      {/* KPI Cards */}
      <section style={{ marginBottom: '2rem' }}>
        <KpiCards />
      </section>

      {/* Action Queues */}
      <section>
        <ActionQueues />
      </section>
    </div>
  );
}
