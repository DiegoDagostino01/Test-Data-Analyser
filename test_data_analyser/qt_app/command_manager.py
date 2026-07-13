"""Central QAction registration and search for application commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QWidget


CommandHandler = Callable[[], object]
AvailabilityPredicate = Callable[[], bool]


@dataclass(frozen=True)
class CommandDefinition:
    command_id: str
    title: str
    category: str
    aliases: tuple[str, ...]
    tooltip: str
    disabled_reason: str
    action: QAction
    availability: AvailabilityPredicate | None = None

    @property
    def search_text(self) -> str:
        return " ".join(
            (self.command_id, self.title, self.category, *self.aliases)
        ).casefold()


class CommandManager:
    """Own every reusable application command and its single QAction."""

    def __init__(self, parent: QWidget) -> None:
        self.parent = parent
        self._commands: dict[str, CommandDefinition] = {}
        self._shortcut_owners: dict[str, str] = {}

    def register(
        self,
        command_id: str,
        title: str,
        handler: CommandHandler | None,
        *,
        category: str,
        aliases: tuple[str, ...] = (),
        shortcut: str = "",
        tooltip: str = "",
        checkable: bool = False,
        checked: bool = False,
        availability: AvailabilityPredicate | None = None,
        disabled_reason: str = "",
    ) -> QAction:
        normalized_id = command_id.strip()
        if not normalized_id or normalized_id in self._commands:
            raise ValueError(f"Duplicate or empty command ID: {command_id!r}")
        normalized_shortcut = QKeySequence(shortcut).toString() if shortcut else ""
        if normalized_shortcut:
            owner = self._shortcut_owners.get(normalized_shortcut)
            if owner is not None:
                raise ValueError(
                    f"Shortcut {normalized_shortcut!r} is already assigned to {owner!r}."
                )

        action = QAction(title.strip(), self.parent)
        action.setObjectName(f"command.{normalized_id}")
        action.setCheckable(checkable)
        if checkable:
            action.setChecked(checked)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        if normalized_shortcut:
            action.setShortcut(QKeySequence(normalized_shortcut))
            self._shortcut_owners[normalized_shortcut] = normalized_id
        self.parent.addAction(action)
        if handler is not None:
            action.triggered.connect(lambda _checked=False: handler())

        definition = CommandDefinition(
            command_id=normalized_id,
            title=title.strip(),
            category=category.strip(),
            aliases=tuple(alias.strip() for alias in aliases if alias.strip()),
            tooltip=tooltip.strip(),
            disabled_reason=disabled_reason.strip(),
            action=action,
            availability=availability,
        )
        self._commands[normalized_id] = definition
        self.refresh_availability(normalized_id)
        return action

    def definition(self, command_id: str) -> CommandDefinition:
        try:
            return self._commands[command_id]
        except KeyError as exc:
            raise KeyError(f"Unknown application command: {command_id}") from exc

    def action(self, command_id: str) -> QAction:
        return self.definition(command_id).action

    def definitions(self) -> tuple[CommandDefinition, ...]:
        return tuple(self._commands.values())

    def refresh_availability(self, command_id: str | None = None) -> None:
        definitions = (
            (self.definition(command_id),)
            if command_id is not None
            else self.definitions()
        )
        for definition in definitions:
            enabled = (
                True
                if definition.availability is None
                else bool(definition.availability())
            )
            definition.action.setEnabled(enabled)

    def disabled_reason(self, command_id: str) -> str:
        definition = self.definition(command_id)
        return "" if definition.action.isEnabled() else definition.disabled_reason

    def search(self, query: str) -> list[CommandDefinition]:
        terms = tuple(term for term in query.casefold().split() if term)
        matches = [
            definition
            for definition in self._commands.values()
            if definition.action.isVisible()
            and all(term in definition.search_text for term in terms)
        ]
        return sorted(
            matches,
            key=lambda definition: (
                not definition.action.isEnabled(),
                definition.category.casefold(),
                definition.title.casefold(),
            ),
        )

    def __contains__(self, command_id: object) -> bool:
        return command_id in self._commands

    def __len__(self) -> int:
        return len(self._commands)
