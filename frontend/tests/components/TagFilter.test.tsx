import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import TagFilter from "../../src/components/TagFilter";

const tags = [
  { tag_id: 1, tag_name: "Adventure" },
  { tag_id: 2, tag_name: "Magic" },
  { tag_id: 3, tag_name: "Time Travel" },
];

function renderTagFilter(props: Partial<React.ComponentProps<typeof TagFilter>> = {}) {
  const onActivate = vi.fn();
  const onChange = vi.fn();

  render(
    <TagFilter
      tags={tags}
      selectedTagId=""
      isLoading={false}
      isError={false}
      onActivate={onActivate}
      onChange={onChange}
      {...props}
    />,
  );

  return { onActivate, onChange };
}

describe("TagFilter", () => {
  test("does not render suggestions before the control is opened", () => {
    renderTagFilter();

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  test("activates loading and selects a matching tag", () => {
    const { onActivate, onChange } = renderTagFilter();
    const input = screen.getByRole("combobox", { name: /^tag$/i });

    fireEvent.focus(input);
    expect(onActivate).toHaveBeenCalledTimes(1);

    fireEvent.change(input, { target: { value: "mag" } });

    expect(screen.getAllByRole("option")).toHaveLength(1);
    fireEvent.pointerDown(screen.getByRole("option", { name: "Magic" }));

    expect(onChange).toHaveBeenCalledWith(2);
    expect(input).toHaveValue("Magic");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  test("renders at most fifty suggestions", () => {
    const manyTags = Array.from({ length: 200 }, (_, index) => ({
      tag_id: index + 1,
      tag_name: `Tag ${String(index + 1).padStart(3, "0")}`,
    }));

    renderTagFilter({ tags: manyTags });
    fireEvent.focus(screen.getByRole("combobox", { name: /^tag$/i }));

    expect(screen.getAllByRole("option")).toHaveLength(50);
  });

  test("restores a selected tag name and clears it", () => {
    const { onChange } = renderTagFilter({ selectedTagId: 2 });
    const input = screen.getByRole("combobox", { name: /^tag$/i });

    expect(input).toHaveValue("Magic");

    fireEvent.pointerDown(screen.getByRole("button", { name: /clear tag filter/i }));
    fireEvent.click(screen.getByRole("button", { name: /clear tag filter/i }));

    expect(onChange).toHaveBeenCalledWith("");
    expect(input).toHaveValue("");
  });

  test("supports keyboard selection", () => {
    const { onChange } = renderTagFilter();
    const input = screen.getByRole("combobox", { name: /^tag$/i });

    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith(2);
    expect(input).toHaveValue("Magic");
  });

  test("lets a user search for a replacement without clearing their text", () => {
    const { onChange } = renderTagFilter({ selectedTagId: 2 });
    const input = screen.getByRole("combobox", { name: /^tag$/i });

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "time" } });

    expect(input).toHaveValue("time");
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.pointerDown(screen.getByRole("option", { name: "Time Travel" }));

    expect(onChange).toHaveBeenCalledWith(3);
    expect(input).toHaveValue("Time Travel");
  });

  test("shows loading, error, and empty states", () => {
    const { rerender } = render(
      <TagFilter
        tags={[]}
        selectedTagId=""
        isLoading
        isError={false}
        onActivate={vi.fn()}
        onChange={vi.fn()}
      />,
    );

    fireEvent.focus(screen.getByRole("combobox", { name: /^tag$/i }));
    expect(screen.getByText(/loading tags/i)).toBeInTheDocument();

    rerender(
      <TagFilter
        tags={[]}
        selectedTagId=""
        isLoading={false}
        isError
        onActivate={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/couldn't load tags/i)).toBeInTheDocument();

    rerender(
      <TagFilter
        tags={[]}
        selectedTagId=""
        isLoading={false}
        isError={false}
        onActivate={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/no matching tags/i)).toBeInTheDocument();
  });
});
