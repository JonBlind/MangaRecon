import { useQuery } from "@tanstack/react-query";
import {
  getRecommendationsForCollection,
  getRecommendationsForQueryList,
} from "../api/recommendations";

import type {
  RecommendationPage,
  RecommendationParams,
  RecommendationQueryListPayload,
} from "../types/recommendation";

export const recommendationKeys = {
  all: ["recommendations"] as const,
  collections: ["recommendations", "collection"] as const,
  collectionRoot: (collectionId: number) =>
    ["recommendations", "collection", collectionId] as const,
  collection: (collectionId: number, params: RecommendationParams) =>
    ["recommendations", "collection", collectionId, params] as const,
  queryLists: ["recommendations", "query-list"] as const,
  queryList: (payload: RecommendationQueryListPayload, params: RecommendationParams) =>
    ["recommendations", "query-list", payload, params] as const,
};

type UseCollectionRecommendationsArgs = {
  collectionId: number;
  params?: RecommendationParams;
  enabled?: boolean;
};

export function useCollectionRecommendations({
  collectionId,
  params = {},
  enabled = true,
}: UseCollectionRecommendationsArgs) {
  return useQuery<RecommendationPage>({
    queryKey: recommendationKeys.collection(collectionId, params),
    queryFn: () => getRecommendationsForCollection(collectionId, params),
    enabled: enabled && !!collectionId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

type UseQueryListRecommendationsArgs = {
  payload: RecommendationQueryListPayload;
  params?: RecommendationParams;
  enabled?: boolean;
};

export function useQueryListRecommendations({
  payload,
  params = {},
  enabled = true,
}: UseQueryListRecommendationsArgs) {
  return useQuery<RecommendationPage>({
    queryKey: recommendationKeys.queryList(payload, params),
    queryFn: () => getRecommendationsForQueryList(payload, params),
    enabled: enabled && payload.manga_ids.length > 0,
    staleTime: 1000 * 60 * 5,
  });
}
