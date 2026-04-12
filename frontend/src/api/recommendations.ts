import { apiFetch } from "./http";
import type {
  RecommendationPage,
  RecommendationParams,
  RecommendationQueryListPayload,
} from "../types/recommendation";

function buildRecommendationParams(params: RecommendationParams = {}): string {
  const sp = new URLSearchParams();

  sp.set("page", String(params.page ?? 1));
  sp.set("size", String(params.size ?? 20));
  sp.set("order_by", params.order_by ?? "score");
  sp.set("order_dir", params.order_dir ?? "desc");

  return sp.toString();
}

export async function getRecommendationsForCollection(collectionId: number, params: RecommendationParams = {}): Promise<RecommendationPage> {
  const qs = buildRecommendationParams(params);
  const res = await apiFetch<RecommendationPage>(`/recommendations/${collectionId}?${qs}`,
    {
      method: "GET",
    }
  );

  return res.data;
}

export async function getRecommendationsForQueryList(payload: RecommendationQueryListPayload, params: RecommendationParams = {}): Promise<RecommendationPage> {
  const qs = buildRecommendationParams(params);
  const res = await apiFetch<RecommendationPage>(
    `/recommendations/query-list?${qs}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );

  return res.data;
}