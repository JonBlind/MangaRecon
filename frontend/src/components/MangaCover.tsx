import { useState } from "react";

type MangaCoverProps = {
  src?: string | null;
  alt: string;
  className?: string;
  imageClassName?: string;
  loading?: "eager" | "lazy";
  decoding?: "async" | "auto" | "sync";
  fetchPriority?: "high" | "low" | "auto";
};

function joinClassNames(...classNames: Array<string | undefined>) {
  return classNames.filter(Boolean).join(" ");
}

export default function MangaCover({
  src,
  alt,
  className,
  imageClassName,
  loading,
  decoding,
  fetchPriority,
}: MangaCoverProps) {
  const normalizedSource = src?.trim() || null;
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const coverIsUnavailable =
    normalizedSource === null || failedSource === normalizedSource;

  if (coverIsUnavailable) {
    return (
      <div
        role="img"
        aria-label={`${alt} cover unavailable`}
        className={joinClassNames(
          className,
          "flex items-center justify-center bg-neutral-200 px-4 text-center font-semibold text-neutral-500",
        )}
      >
        <span aria-hidden="true">No Cover</span>
      </div>
    );
  }

  return (
    <img
      src={normalizedSource}
      alt={alt}
      className={joinClassNames(className, imageClassName)}
      loading={loading}
      decoding={decoding}
      fetchPriority={fetchPriority}
      onError={() => setFailedSource(normalizedSource)}
    />
  );
}
