import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";

const SITE_NAME = "MangaRecon";
const SITE_URL = "https://mangarecon.com/";
const LANDING_TITLE = "MangaRecon - Discover Manga";

function getOrCreateMeta(name: string): HTMLMetaElement {
  const existing = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  if (existing) return existing;

  const meta = document.createElement("meta");
  meta.name = name;
  document.head.append(meta);
  return meta;
}

function getOrCreateCanonical(): HTMLLinkElement {
  const existing = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (existing) return existing;

  const canonical = document.createElement("link");
  canonical.rel = "canonical";
  document.head.append(canonical);
  return canonical;
}

export default function SearchMetadata() {
  const { pathname } = useLocation();

  useEffect(() => {
    const isLandingPage = pathname === "/";
    const robots = getOrCreateMeta("robots");

    document.title = isLandingPage ? LANDING_TITLE : SITE_NAME;
    robots.content = isLandingPage ? "index, follow" : "noindex, follow";

    if (isLandingPage) {
      getOrCreateCanonical().href = SITE_URL;
    } else {
      document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.remove();
    }
  }, [pathname]);

  return <Outlet />;
}
