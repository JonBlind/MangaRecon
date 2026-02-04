import { apiFetch } from "./http";
import type { Genre, Tag, Demographic, MetadataListResponse } from "../types/metadata";

export async function getGenres(): Promise<Genre[]> {
  const res = await apiFetch<MetadataListResponse<Genre>>("/metadata/genres");
  return res.data.items;
}

export async function getTags(): Promise<Tag[]> {
  const res = await apiFetch<MetadataListResponse<Tag>>("/metadata/tags");
  return res.data.items;
}

export async function getDemographics(): Promise<Demographic[]> {
  const res = await apiFetch<MetadataListResponse<Demographic>>("/metadata/demographics");
  return res.data.items;
}