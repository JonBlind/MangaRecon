import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import MetadataMultiSelect, {
  type MetadataSelection,
} from "../../src/components/MetadataMultiSelect";

const options = [
  { id: 1, label: "Adventure" },
  { id: 2, label: "Magic" },
  { id: 3, label: "Time Travel" },
];

function StatefulFilter({
  initialSelection = { includedIds: [], excludedIds: [] },
  onActivate = vi.fn(),
  onSelectionChange = vi.fn(),
}: {
  initialSelection?: MetadataSelection;
  onActivate?: () => void;
  onSelectionChange?: (selection: MetadataSelection) => void;
}) {
  const [selection, setSelection] = useState(initialSelection);

  return (
    <MetadataMultiSelect
      label="Tag"
      options={options}
      includedIds={selection.includedIds}
      excludedIds={selection.excludedIds}
      placeholder="Any tag"
      isLoading={false}
      isError={false}
      searchable
      onActivate={onActivate}
      onChange={(nextSelection) => {
        onSelectionChange(nextSelection);
        setSelection(nextSelection);
      }}
    />
  );
}

describe("MetadataMultiSelect", () => {
  test("does not render options before it is opened", () => {
    render(<StatefulFilter />);

    expect(screen.queryByRole("group", { name: /tag options/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  test("cycles each option from included to excluded to clear", () => {
    const onActivate = vi.fn();
    const onSelectionChange = vi.fn();
    render(
      <StatefulFilter onActivate={onActivate} onSelectionChange={onSelectionChange} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));
    expect(onActivate).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("checkbox", { name: /adventure/i }));
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      includedIds: [1],
      excludedIds: [],
    });
    expect(
      screen.getByRole("checkbox", { name: /adventure: included/i }),
    ).toHaveTextContent("✓");

    fireEvent.click(screen.getByRole("checkbox", { name: /adventure/i }));
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      includedIds: [],
      excludedIds: [1],
    });
    expect(
      screen.getByRole("checkbox", { name: /adventure: excluded/i }),
    ).toHaveTextContent("×");

    fireEvent.click(screen.getByRole("checkbox", { name: /adventure/i }));
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      includedIds: [],
      excludedIds: [],
    });
    expect(
      screen.getByRole("checkbox", { name: /adventure: not selected/i }),
    ).toHaveTextContent("Adventure");
  });

  test("keeps multiple included and excluded values", () => {
    const onSelectionChange = vi.fn();
    render(<StatefulFilter onSelectionChange={onSelectionChange} />);

    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /adventure/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /magic/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /magic/i }));

    expect(onSelectionChange).toHaveBeenLastCalledWith({
      includedIds: [1],
      excludedIds: [2],
    });
    expect(screen.getByRole("button", { name: /tag filter/i })).toHaveTextContent(
      "1 included · 1 excluded",
    );
  });

  test("searches available options", () => {
    render(<StatefulFilter />);
    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));

    fireEvent.change(screen.getByRole("searchbox", { name: /search tag options/i }), {
      target: { value: "time" },
    });

    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    expect(screen.getByRole("checkbox", { name: /time travel/i })).toBeInTheDocument();
  });

  test("renders at most fifty options", () => {
    const manyOptions = Array.from({ length: 200 }, (_, index) => ({
      id: index + 1,
      label: `Tag ${String(index + 1).padStart(3, "0")}`,
    }));

    render(
      <MetadataMultiSelect
        label="Tag"
        options={manyOptions}
        includedIds={[]}
        excludedIds={[]}
        placeholder="Any tag"
        isLoading={false}
        isError={false}
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));

    expect(screen.getAllByRole("checkbox")).toHaveLength(50);
  });

  test("clears every included and excluded value", () => {
    const onSelectionChange = vi.fn();
    render(
      <StatefulFilter
        initialSelection={{ includedIds: [1, 2], excludedIds: [3] }}
        onSelectionChange={onSelectionChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));
    fireEvent.click(screen.getByRole("button", { name: /clear all/i }));

    expect(onSelectionChange).toHaveBeenCalledWith({
      includedIds: [],
      excludedIds: [],
    });
    expect(screen.getByRole("button", { name: /tag filter/i })).toHaveTextContent(
      "Any tag",
    );
  });

  test("shows loading, error, and empty states", () => {
    const baseProps = {
      label: "Tag",
      options: [],
      includedIds: [],
      excludedIds: [],
      placeholder: "Any tag",
      onChange: vi.fn(),
    };
    const { rerender } = render(
      <MetadataMultiSelect {...baseProps} isLoading isError={false} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));
    expect(screen.getByText(/loading tags/i)).toBeInTheDocument();

    rerender(<MetadataMultiSelect {...baseProps} isLoading={false} isError />);
    expect(screen.getByText(/couldn't load tags/i)).toBeInTheDocument();

    rerender(<MetadataMultiSelect {...baseProps} isLoading={false} isError={false} />);
    expect(screen.getByText(/no matching tags/i)).toBeInTheDocument();
  });

  test("closes when the user clicks outside", () => {
    render(
      <div>
        <StatefulFilter />
        <button type="button">Outside</button>
      </div>,
    );
    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));
    expect(screen.getByRole("checkbox", { name: /adventure/i })).toBeInTheDocument();

    fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));
    expect(
      screen.queryByRole("checkbox", { name: /adventure/i }),
    ).not.toBeInTheDocument();
  });

  test("closes from the search field when Escape is pressed", () => {
    render(<StatefulFilter />);
    fireEvent.click(screen.getByRole("button", { name: /tag filter/i }));

    fireEvent.keyDown(screen.getByRole("searchbox", { name: /search tag options/i }), {
      key: "Escape",
    });

    expect(
      screen.queryByRole("checkbox", { name: /adventure/i }),
    ).not.toBeInTheDocument();
  });
});
