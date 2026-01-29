import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Collections() {
  const nav = useNavigate();
  const { clearAuthToken } = useAuth();

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Collections</h1>
        <button
          className="rounded-xl border px-3 py-2 text-sm"
          onClick={() => {
            clearAuthToken();
            nav("/login");
          }}
        >
          Logout
        </button>
      </div>

      <div className="opacity-70">TODO: list collections here</div>
    </div>
  );
}
