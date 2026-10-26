import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './components/ui/Toast';
import { Spinner } from './components/ui/Spinner';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/layout/ProtectedRoute';

// Route-level code splitting via React.lazy
const LoginPage = React.lazy(() => import('./pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = React.lazy(() => import('./pages/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })));
const NotAllowedPage = React.lazy(() => import('./pages/NotAllowedPage').then((m) => ({ default: m.NotAllowedPage })));
const NotFoundPage = React.lazy(() => import('./pages/NotAllowedPage').then((m) => ({ default: m.NotFoundPage })));
const NotificationsPage = React.lazy(() => import('./pages/NotificationsPage').then((m) => ({ default: m.NotificationsPage })));
const PublicBookingPage = React.lazy(() => import('./pages/booking/PublicBookingPage').then((m) => ({ default: m.PublicBookingPage })));

// Coordinator Pages
const CoordinatorDashboard = React.lazy(() => import('./pages/coordinator/CoordinatorDashboard').then((m) => ({ default: m.CoordinatorDashboard })));
const PeoplePage = React.lazy(() => import('./pages/coordinator/PeoplePage').then((m) => ({ default: m.PeoplePage })));
const RoomsPage = React.lazy(() => import('./pages/coordinator/RoomsPage').then((m) => ({ default: m.RoomsPage })));
const RoomAvailabilityPage = React.lazy(() => import('./pages/coordinator/RoomAvailabilityPage').then((m) => ({ default: m.RoomAvailabilityPage })));
const UserAvailabilityPage = React.lazy(() => import('./pages/coordinator/UserAvailabilityPage').then((m) => ({ default: m.UserAvailabilityPage })));
const DrivesPage = React.lazy(() => import('./pages/coordinator/DrivesPage').then((m) => ({ default: m.DrivesPage })));
const DriveDetailPage = React.lazy(() => import('./pages/coordinator/DriveDetailPage').then((m) => ({ default: m.DriveDetailPage })));
const AICopilotPage = React.lazy(() => import('./pages/coordinator/AICopilotPage').then((m) => ({ default: m.AICopilotPage })));
const AnalyticsDashboardPage = React.lazy(() => import('./pages/coordinator/AnalyticsDashboardPage').then((m) => ({ default: m.AnalyticsDashboardPage })));

// Candidate Pages
const CandidateDashboard = React.lazy(() => import('./pages/candidate/CandidateDashboard').then((m) => ({ default: m.CandidateDashboard })));
const CandidateAvailabilityPage = React.lazy(() => import('./pages/candidate/CandidateAvailabilityPage').then((m) => ({ default: m.CandidateAvailabilityPage })));

// Interviewer Pages
const InterviewerDashboard = React.lazy(() => import('./pages/interviewer/InterviewerDashboard').then((m) => ({ default: m.InterviewerDashboard })));
const InterviewerAvailabilityPage = React.lazy(() => import('./pages/interviewer/InterviewerAvailabilityPage').then((m) => ({ default: m.InterviewerAvailabilityPage })));
const InterviewerProfilePage = React.lazy(() => import('./pages/interviewer/InterviewerProfilePage').then((m) => ({ default: m.InterviewerProfilePage })));
const InterviewerInterviewsPage = React.lazy(() => import('./pages/interviewer/InterviewerInterviewsPage').then((m) => ({ default: m.InterviewerInterviewsPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const PageFallback: React.FC = () => (
  <div className="min-h-[50vh] flex items-center justify-center p-8">
    <Spinner size="lg" label="Loading view..." />
  </div>
);

// Root index redirect based on auth status
const RootRedirect: React.FC = () => {
  const { isAuthenticated, role, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <Spinner size="lg" label="Initializing InterviewOS..." />
      </div>
    );
  }

  if (isAuthenticated && role) {
    return <Navigate to={`/${role}`} replace />;
  }

  return <Navigate to="/login" replace />;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                {/* Public Routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/book/:token" element={<PublicBookingPage />} />
                <Route path="/not-allowed" element={<NotAllowedPage />} />

                {/* Coordinator Area */}
                <Route
                  path="/coordinator/*"
                  element={
                    <ProtectedRoute allowedRoles={['coordinator']}>
                      <AppShell>
                        <Suspense fallback={<PageFallback />}>
                          <Routes>
                            <Route path="" element={<CoordinatorDashboard />} />
                            <Route path="people" element={<PeoplePage />} />
                            <Route path="rooms" element={<RoomsPage />} />
                            <Route path="rooms/:roomId/availability" element={<RoomAvailabilityPage />} />
                            <Route path="users/:userId/availability" element={<UserAvailabilityPage />} />
                            <Route path="drives" element={<DrivesPage />} />
                            <Route path="drives/new" element={<DrivesPage />} />
                            <Route path="drives/:driveId" element={<DriveDetailPage />} />
                            <Route path="ai-copilot" element={<AICopilotPage />} />
                            <Route path="analytics" element={<AnalyticsDashboardPage />} />
                            <Route path="*" element={<CoordinatorDashboard />} />
                          </Routes>
                        </Suspense>
                      </AppShell>
                    </ProtectedRoute>
                  }
                />

                {/* Candidate Area */}
                <Route
                  path="/candidate/*"
                  element={
                    <ProtectedRoute allowedRoles={['candidate']}>
                      <AppShell>
                        <Suspense fallback={<PageFallback />}>
                          <Routes>
                            <Route path="" element={<CandidateDashboard />} />
                            <Route path="interviews" element={<CandidateDashboard focusProgress />} />
                            <Route path="availability" element={<CandidateAvailabilityPage />} />
                            <Route path="*" element={<CandidateDashboard />} />
                          </Routes>
                        </Suspense>
                      </AppShell>
                    </ProtectedRoute>
                  }
                />

                {/* Interviewer Area */}
                <Route
                  path="/interviewer/*"
                  element={
                    <ProtectedRoute allowedRoles={['interviewer']}>
                      <AppShell>
                        <Suspense fallback={<PageFallback />}>
                          <Routes>
                            <Route path="" element={<InterviewerDashboard />} />
                            <Route path="interviews" element={<InterviewerInterviewsPage />} />
                            <Route path="availability" element={<InterviewerAvailabilityPage />} />
                            <Route path="profile" element={<InterviewerProfilePage />} />
                            <Route path="*" element={<InterviewerDashboard />} />
                          </Routes>
                        </Suspense>
                      </AppShell>
                    </ProtectedRoute>
                  }
                />

                {/* Shared Authenticated Routes */}
                <Route
                  path="/notifications"
                  element={
                    <ProtectedRoute>
                      <AppShell>
                        <Suspense fallback={<PageFallback />}>
                          <NotificationsPage />
                        </Suspense>
                      </AppShell>
                    </ProtectedRoute>
                  }
                />

                {/* Index & Fallback */}
                <Route path="/" element={<RootRedirect />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
