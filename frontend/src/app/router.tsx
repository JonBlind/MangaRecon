import { createBrowserRouter } from "react-router-dom";
import Layout from "../components/Layout";
import ProtectedRoute from "../components/ProtectedRoute";

import Landing from "../pages/Landing";

export const router = createBrowserRouter([
  {
    path: "/maintenance",
    lazy: async () => ({
      Component: (await import("../pages/Maintenance")).default,
    }),
  },
  {
    path: "/",
    element: <Layout />,
    children: [
      { path: "/", element: <Landing /> },
      {
        path: "/login",
        lazy: async () => ({
          Component: (await import("../pages/Login")).default,
        }),
      },
      {
        path: "/register",
        lazy: async () => ({
          Component: (await import("../pages/Register")).default,
        }),
      },
      {
        path: "/verify-email",
        lazy: async () => ({
          Component: (await import("../pages/VerifyEmail")).default,
        }),
      },
      {
        path: "/forgot-password",
        lazy: async () => ({
          Component: (await import("../pages/ForgotPassword")).default,
        }),
      },
      {
        path: "/reset-password",
        lazy: async () => ({
          Component: (await import("../pages/ResetPassword")).default,
        }),
      },
      {
        path: "/search",
        lazy: async () => ({
          Component: (await import("../pages/Search")).default,
        }),
      },
      {
        path: "/manga/:id",
        lazy: async () => ({
          Component: (await import("../pages/MangaDetail")).default,
        }),
      },

      {
        element: <ProtectedRoute />,
        children: [
          {
            path: "collections",
            lazy: async () => ({
              Component: (await import("../pages/Collections")).default,
            }),
          },
          {
            path: "collections/:id",
            lazy: async () => ({
              Component: (await import("../pages/CollectionDetail")).default,
            }),
          },
          {
            path: "recommendations",
            lazy: async () => ({
              Component: (await import("../pages/Recommendations")).default,
            }),
          },
          {
            path: "/account",
            lazy: async () => ({
              Component: (await import("../pages/Account")).default,
            }),
          },
        ],
      },
    ],
  },
]);
