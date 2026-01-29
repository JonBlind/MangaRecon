import { Navigate } from "react-router-dom";
import { useMe } from "../hooks/useMe";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useMe();

  if (isLoading) return <div className="p-4">Loading...</div>;
  if (isError || !data) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
