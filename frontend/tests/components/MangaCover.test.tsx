import { fireEvent, render, screen } from "@testing-library/react";
import MangaCover from "../../src/components/MangaCover";

describe("MangaCover", () => {
  test("renders an available cover image", () => {
    render(<MangaCover src="https://example.com/naruto.jpg" alt="Naruto" />);

    expect(screen.getByAltText("Naruto")).toHaveAttribute(
      "src",
      "https://example.com/naruto.jpg",
    );
  });

  test.each([null, undefined, "   "])(
    "renders the local fallback when the source is %s",
    (src) => {
      render(<MangaCover src={src} alt="Naruto" />);

      expect(
        screen.getByRole("img", { name: "Naruto cover unavailable" }),
      ).toHaveTextContent("No Cover");
      expect(screen.queryByAltText("Naruto")).not.toBeInTheDocument();
    },
  );

  test("replaces a failed cover request with the local fallback", () => {
    render(<MangaCover src="https://example.com/missing.jpg" alt="Naruto" />);

    fireEvent.error(screen.getByAltText("Naruto"));

    expect(
      screen.getByRole("img", { name: "Naruto cover unavailable" }),
    ).toHaveTextContent("No Cover");
    expect(screen.queryByAltText("Naruto")).not.toBeInTheDocument();
  });

  test("tries a new source after the previous source failed", () => {
    const { rerender } = render(
      <MangaCover src="https://example.com/missing.jpg" alt="Naruto" />,
    );

    fireEvent.error(screen.getByAltText("Naruto"));

    rerender(<MangaCover src="https://example.com/replacement.jpg" alt="Naruto" />);

    expect(screen.getByAltText("Naruto")).toHaveAttribute(
      "src",
      "https://example.com/replacement.jpg",
    );
  });
});
