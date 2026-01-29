import { createBrowserRouter } from "react-router-dom";
import Login from "../pages/Login";
import Register from "../pages/Register";
import VerifyEmail from "../pages/VerifyEmail";
import Search from "../pages/Search";
import Collections from "../pages/Collections";
import CollectionDetail from "../pages/CollectionDetail";
import Recommendations from "../pages/Recommendations";
import ProtectedRoute from "../components/ProtectedRoute";
import Landing from "../pages/Landing";

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  { path: "/verify-email", element: <VerifyEmail /> },
  { path: "/search", element: <Search /> },
  { path: "/", element: <Landing /> },

  {
    path: "/collections",
    element: (
      <ProtectedRoute>
        <Collections />
      </ProtectedRoute>
    ),
  },
  {
    path: "/collections/:id",
    element: (
      <ProtectedRoute>
        <CollectionDetail />
      </ProtectedRoute>
    ),
  },
  {
    path: "/recommendations/:id",
    element: (
      <ProtectedRoute>
        <Recommendations />
      </ProtectedRoute>
    ),
  },
]);
