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
  { path: "/", element: <Landing /> },
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  { path: "/verify-email", element: <VerifyEmail /> },
  { path: "/search", element: <Search /> },

  // Protected routes
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/collections", element: <Collections /> },
      { path: "/collections/:id", element: <CollectionDetail /> },
      { path: "/recommendations/:id", element: <Recommendations /> },
    ],
  },
]);
