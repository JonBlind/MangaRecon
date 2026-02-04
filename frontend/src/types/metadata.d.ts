export type Genre = {
  genre_id: number;
  genre_name: string;
};

export type Tag = {
  tag_id: number;
  tag_name: string;
};

export type Demographic = {
  demographic_id: number;
  demographic_name: string;
};

export type MetadataListResponse<T> = {
  items: T[];
};