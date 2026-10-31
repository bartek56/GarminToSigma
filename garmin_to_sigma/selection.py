"""Selection of activities from a displayed list."""

import re


class ActivitySelection:
    def __init__(self, item_count: int):
        self.item_count = item_count

    def indices(self, selection: str) -> list[int]:
        selection = selection.strip().lower()
        if not selection or selection == "all":
            return list(range(self.item_count))

        selected = set()
        for part in selection.split(","):
            part = part.strip()
            range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
            if range_match:
                first, last = map(int, range_match.groups())
                if first > last:
                    raise ValueError("Range must be in ascending order.")
                selected.update(range(first, last + 1))
                continue
            if not part.isdigit():
                raise ValueError("Use numbers, comma-separated numbers, or ranges.")
            selected.add(int(part))

        if not selected or min(selected) < 1 or max(selected) > self.item_count:
            raise ValueError("Choose numbers from the displayed list.")
        return [index - 1 for index in sorted(selected)]
