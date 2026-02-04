import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useMe } from "../hooks/useMe";

export default function ProtectedRoute() {
  const { data: me, isPending, isFetching, isError } = useMe();
  const loc = useLocation();

  if (isPending || isFetching) {
    return <div className="p-4">Loading...</div>;
  }

  if (isError || !me) {
    console.log("[ProtectedRoute]", { isPending, isFetching, isError, me });
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }

  return <Outlet />;
}