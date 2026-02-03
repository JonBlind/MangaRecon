import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useMe } from "../hooks/useMe";

export default function ProtectedRoute() {
  const { data, isLoading, isError } = useMe();
  const loc = useLocation();

  if (isLoading) return <div className="p-4">Loading...</div>;

  if (isError || !data) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }

  return <Outlet />;
}
