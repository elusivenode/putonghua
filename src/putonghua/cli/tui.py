"""Interactive terminal session shell."""

from __future__ import annotations

import readline
from collections.abc import Callable
from dataclasses import dataclass
from textwrap import wrap

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from putonghua.models.tui import (
    TuiCandidateView,
    TuiChunkView,
    TuiDashboardView,
    TuiPublishTargetView,
    TuiReviewContextView,
)
from putonghua.models.tutorial import TutorialSessionView, TutorialStepView
from putonghua.services.tui_session import TuiSessionService

InputFunc = Callable[[str], str]
FOCUS_WRAP_WIDTH = 88

HELP_TEXT = (
    "Shortcuts: [bold]h[/] help, [bold]r[/] refresh, [bold]p N[/] project, "
    "[bold]s N[/] source, [bold]c N[/] chunk, [bold]n[/] next pending chunk, "
    "[bold]done[/] mark chunk completed, "
    "[bold]extract[/] extract candidates, [bold]chat PROMPT[/] review prompt, "
    "[bold]promote [N][/] promote candidate, [bold]publish [N][/] publish candidate, "
    "[bold]tutorial[/] start fresh tutorial, "
    "[bold]tutorial resume[/] resume tutorial, "
    "[bold]tutorial next[/] advance guided intro, "
    "[bold]tutorial status[/] show progress, "
    "[bold]tutorial reset[/] clear tutorial state, "
    "[bold]q[/] quit"
)


@dataclass
class TuiSessionState:
    """Current session selection state."""

    selected_project_id: str | None = None
    selected_source_id: str | None = None
    selected_chunk_id: str | None = None


def run_tui_session(
    *,
    service: TuiSessionService,
    console: Console,
    input_func: InputFunc,
) -> None:
    """Run the interactive terminal session loop."""

    state = TuiSessionState()
    console.print("Putonghua TUI session")
    console.print("Type `help` for commands. Select a project, source, and chunk.")

    while True:
        dashboard = service.get_dashboard(
            selected_project_id=state.selected_project_id,
            selected_source_id=state.selected_source_id,
            selected_chunk_id=state.selected_chunk_id,
        )
        state.selected_project_id = dashboard.selected_project_id
        state.selected_source_id = dashboard.selected_source_id
        state.selected_chunk_id = dashboard.selected_chunk_id

        _render_dashboard(console, dashboard)

        raw_command = input_func("putonghua> ").strip()
        if not raw_command:
            continue
        _remember_command(raw_command)
        should_exit = _handle_command(
            raw_command=raw_command,
            dashboard=dashboard,
            state=state,
            service=service,
            console=console,
            input_func=input_func,
        )
        if should_exit:
            return


def _remember_command(command: str) -> None:
    """Add one entered TUI command to the current terminal history."""

    readline.add_history(command)


def _handle_command(
    *,
    raw_command: str,
    dashboard: TuiDashboardView,
    state: TuiSessionState,
    service: TuiSessionService,
    console: Console,
    input_func: InputFunc,
) -> bool:
    """Apply one command to the current session."""

    command, _, argument_text = raw_command.partition(" ")
    normalized = command.lower()
    arguments = argument_text.split() if argument_text else []

    if normalized in {"q", "quit", "exit"}:
        console.print("Leaving putonghua TUI.")
        return True
    if normalized in {"h", "help", "?"}:
        console.print(HELP_TEXT)
        return False
    if normalized in {"r", "refresh"}:
        console.print("Refreshed session state.")
        return False
    if normalized in {"n", "next"}:
        next_chunk = _find_next_pending_chunk(dashboard.chunks)
        if next_chunk is None:
            console.print("No pending chunk available in the current source.")
            return False
        state.selected_chunk_id = next_chunk.id
        console.print(f"Selected chunk {next_chunk.chunk_index + 1}.")
        return False
    if normalized in {"done", "complete"}:
        return _complete_selected_chunk(
            dashboard=dashboard,
            state=state,
            service=service,
            console=console,
        )
    if normalized in {"p", "project"}:
        return _select_project(arguments, dashboard, state, console)
    if normalized in {"s", "source"}:
        return _select_source(arguments, dashboard, state, console)
    if normalized in {"c", "chunk"}:
        return _select_chunk(arguments, dashboard, state, console)
    if normalized == "tutorial":
        return _handle_tutorial_command(
            arguments=arguments,
            state=state,
            service=service,
            console=console,
        )
    if normalized == "extract":
        return _extract_selected_chunk(
            dashboard=dashboard,
            service=service,
            console=console,
        )
    if normalized == "promote":
        return _promote_selected_suggestion(
            arguments=arguments,
            dashboard=dashboard,
            service=service,
            console=console,
        )
    if normalized == "chat":
        return _chat_for_selected_chunk(
            argument_text=argument_text,
            dashboard=dashboard,
            service=service,
            console=console,
            input_func=input_func,
        )
    if normalized == "publish":
        return _publish_selected_candidate(
            arguments=arguments,
            dashboard=dashboard,
            service=service,
            console=console,
            input_func=input_func,
        )

    console.print(f"Unknown command: {raw_command}")
    console.print(HELP_TEXT)
    return False


def _select_project(
    arguments: list[str],
    dashboard: TuiDashboardView,
    state: TuiSessionState,
    console: Console,
) -> bool:
    """Select a project by 1-based index."""

    index = _parse_index(arguments, console, "project")
    if index is None:
        return False
    if index < 0 or index >= len(dashboard.projects):
        console.print("Project selection is out of range.")
        return False

    selected = dashboard.projects[index]
    state.selected_project_id = selected.id
    state.selected_source_id = None
    state.selected_chunk_id = None
    console.print(f"Selected project: {selected.name}")
    return False


def _select_source(
    arguments: list[str],
    dashboard: TuiDashboardView,
    state: TuiSessionState,
    console: Console,
) -> bool:
    """Select a source by 1-based index."""

    index = _parse_index(arguments, console, "source")
    if index is None:
        return False
    if index < 0 or index >= len(dashboard.sources):
        console.print("Source selection is out of range.")
        return False

    selected = dashboard.sources[index]
    state.selected_source_id = selected.id
    state.selected_chunk_id = None
    console.print(f"Selected source: {selected.title}")
    return False


def _select_chunk(
    arguments: list[str],
    dashboard: TuiDashboardView,
    state: TuiSessionState,
    console: Console,
) -> bool:
    """Select a chunk by 1-based index."""

    index = _parse_index(arguments, console, "chunk")
    if index is None:
        return False
    if index < 0 or index >= len(dashboard.chunks):
        console.print("Chunk selection is out of range.")
        return False

    selected = dashboard.chunks[index]
    state.selected_chunk_id = selected.id
    console.print(f"Selected chunk {selected.chunk_index + 1}.")
    return False


def _handle_tutorial_command(
    *,
    arguments: list[str],
    state: TuiSessionState,
    service: TuiSessionService,
    console: Console,
) -> bool:
    """Start, inspect, or reset the tutorial session."""

    action = arguments[0].lower() if arguments else "start"
    if action == "start":
        try:
            session = service.start_tutorial()
        except Exception as exc:
            console.print(f"Tutorial start failed: {exc}")
            return False
        state.selected_project_id = session.project_id
        state.selected_source_id = session.source_id
        state.selected_chunk_id = session.study_chunk_id
        console.print(
            "Tutorial started from step 1. "
            "Follow the Tutorial panel for the next operator action."
        )
        return False
    if action == "resume":
        try:
            session = service.resume_tutorial()
        except Exception as exc:
            console.print(f"Tutorial resume failed: {exc}")
            return False
        state.selected_project_id = session.project_id
        state.selected_source_id = session.source_id
        state.selected_chunk_id = session.study_chunk_id
        console.print("Tutorial resumed.")
        return False
    if action == "status":
        session = service.get_tutorial_session()
        if session is None:
            console.print("No active tutorial session.")
            return False
        console.print(_render_tutorial_panel(session))
        return False
    if action == "next":
        try:
            session = service.advance_tutorial()
        except Exception as exc:
            console.print(f"Tutorial advance failed: {exc}")
            return False
        state.selected_project_id = session.project_id
        state.selected_source_id = session.source_id
        state.selected_chunk_id = session.study_chunk_id
        console.print("Tutorial advanced.")
        return False
    if action == "reset":
        try:
            reset = service.reset_tutorial()
        except Exception as exc:
            console.print(f"Tutorial reset failed: {exc}")
            return False
        state.selected_project_id = None
        state.selected_source_id = None
        state.selected_chunk_id = None
        if reset:
            console.print(
                "Tutorial state reset. Type `tutorial` to start again from step 1."
            )
        else:
            console.print(
                "No active tutorial session was available to reset. "
                "Type `tutorial` to start from step 1."
            )
        return False

    console.print(
        "Tutorial usage: tutorial, tutorial resume, tutorial next, "
        "tutorial status, tutorial reset"
    )
    return False


def _extract_selected_chunk(
    *,
    dashboard: TuiDashboardView,
    service: TuiSessionService,
    console: Console,
) -> bool:
    """Run extraction for the selected chunk."""

    selected_chunk = _get_selected_chunk(dashboard)
    if selected_chunk is None:
        console.print("Select a chunk before running extraction.")
        return False

    try:
        result = service.extract_chunk(selected_chunk.id)
    except Exception as exc:
        console.print(f"Chunk extraction failed: {exc}")
        return False

    console.print(
        "Extracted "
        f"{result.candidate_count} candidate cards for chunk {result.chunk_id}"
    )
    return False


def _complete_selected_chunk(
    *,
    dashboard: TuiDashboardView,
    state: TuiSessionState,
    service: TuiSessionService,
    console: Console,
) -> bool:
    """Mark the selected chunk completed and move on when possible."""

    selected_chunk = _get_selected_chunk(dashboard)
    if selected_chunk is None:
        console.print("Select a chunk before marking it completed.")
        return False

    try:
        service.complete_chunk(selected_chunk.id)
    except Exception as exc:
        console.print(f"Chunk completion failed: {exc}")
        return False

    next_chunk = next(
        (
            chunk
            for chunk in dashboard.chunks
            if chunk.id != selected_chunk.id and chunk.status == "pending"
        ),
        None,
    )
    if next_chunk is None:
        state.selected_chunk_id = None
        console.print(
            f"Marked chunk {selected_chunk.chunk_index + 1} completed. "
            "No other pending chunk is currently available in this source."
        )
        return False

    state.selected_chunk_id = next_chunk.id
    console.print(
        f"Marked chunk {selected_chunk.chunk_index + 1} completed. "
        f"Selected chunk {next_chunk.chunk_index + 1}."
    )
    return False


def _chat_for_selected_chunk(
    *,
    argument_text: str,
    dashboard: TuiDashboardView,
    service: TuiSessionService,
    console: Console,
    input_func: InputFunc,
) -> bool:
    """Run one chat turn for the selected chunk."""

    selected_chunk = _get_selected_chunk(dashboard)
    if selected_chunk is None:
        console.print("Select a chunk before starting review chat.")
        return False

    prompt = argument_text.strip()
    if not prompt:
        prompt = input_func("chat> ").strip()
    if not prompt:
        console.print("Review chat cancelled.")
        return False

    try:
        result = service.chat_for_chunk(selected_chunk.id, prompt)
    except Exception as exc:
        console.print(f"Chunk chat failed: {exc}")
        return False

    console.print(f"Conversation ID: {result.conversation_id}")
    console.print("Assistant:")
    console.print(result.assistant_text)
    if result.suggested_cards:
        console.print(f"Added candidates: {len(result.suggested_cards)}")
    return False


def _promote_selected_suggestion(
    *,
    arguments: list[str],
    dashboard: TuiDashboardView,
    service: TuiSessionService,
    console: Console,
) -> bool:
    """Promote one candidate into the publish queue."""

    if not dashboard.candidates:
        console.print("No candidates are available for the selected chunk.")
        return False

    candidate = _resolve_promotable_candidate(arguments, dashboard.candidates, console)
    if candidate is None:
        return False

    try:
        result = service.promote_candidate(candidate.id)
    except Exception as exc:
        console.print(f"Candidate promotion failed: {exc}")
        return False

    console.print(f"Candidate ID: {result.candidate_id}")
    console.print(f"Status: {result.status}")
    if result.created:
        console.print("Candidate added to the publish queue")
    else:
        console.print("Candidate was already ready to publish")
    return False


def _parse_index(
    arguments: list[str],
    console: Console,
    label: str,
) -> int | None:
    """Parse a 1-based selection index."""

    if len(arguments) != 1:
        console.print(f"{label.title()} selection requires a 1-based index.")
        return None
    try:
        return int(arguments[0]) - 1
    except ValueError:
        console.print(f"{label.title()} selection requires a numeric index.")
        return None


def _publish_selected_candidate(
    *,
    arguments: list[str],
    dashboard: TuiDashboardView,
    service: TuiSessionService,
    console: Console,
    input_func: InputFunc,
) -> bool:
    """Publish one visible candidate for the selected chunk."""

    if dashboard.publish_target is None:
        console.print(
            "Publish target is not configured. Set anki.default_deck and "
            "anki.default_note_type."
        )
        return False
    if not dashboard.candidates:
        console.print("No candidates are available for the selected chunk.")
        return False

    candidate = _resolve_selected_candidate(arguments, dashboard.candidates, console)
    if candidate is None:
        return False

    if (
        candidate.anki_note_id is not None
        and candidate.publication_status == "published"
    ):
        console.print(
            f"Candidate already published locally as note {candidate.anki_note_id}."
        )

    confirmation = input_func(
        "publish> "
        f"{candidate.simplified or candidate.id} -> "
        f"{dashboard.publish_target.deck_name} / "
        f"{dashboard.publish_target.note_type_name} [y/N]: "
    ).strip()
    if confirmation.lower() not in {"y", "yes"}:
        console.print("Candidate publish cancelled.")
        return False

    try:
        result = service.publish_candidate(candidate.id)
    except Exception as exc:
        console.print(f"Candidate publish failed: {exc}")
        return False

    console.print(f"Deck: {dashboard.publish_target.deck_name}")
    console.print(f"Note Type: {dashboard.publish_target.note_type_name}")
    console.print(f"Candidate ID: {result.candidate_id}")
    console.print(f"Publication Record ID: {result.publication_record_id}")
    console.print(f"Anki Note ID: {result.anki_note_id}")
    console.print(f"Status: {result.status}")
    if result.created:
        console.print("Created new Anki note")
    else:
        console.print("Anki note already existed locally")
        console.print("Skipped remote publish and reused the local publication record")
    return False


def _resolve_selected_candidate(
    arguments: list[str],
    candidates: list[TuiCandidateView],
    console: Console,
) -> TuiCandidateView | None:
    """Resolve the visible candidate to publish."""

    if not arguments:
        for candidate in candidates:
            if candidate.status == "promoted":
                return candidate
        return candidates[0]

    index = _parse_index(arguments, console, "candidate")
    if index is None:
        return None
    if index < 0 or index >= len(candidates):
        console.print("Candidate selection is out of range.")
        return None
    return candidates[index]


def _resolve_promotable_candidate(
    arguments: list[str],
    candidates: list[TuiCandidateView],
    console: Console,
) -> TuiCandidateView | None:
    """Resolve the visible extracted candidate to promote."""

    if not arguments:
        for candidate in candidates:
            if candidate.status not in {"promoted", "published"}:
                return candidate
        return candidates[0]

    index = _parse_index(arguments, console, "candidate")
    if index is None:
        return None
    if index < 0 or index >= len(candidates):
        console.print("Candidate selection is out of range.")
        return None
    return candidates[index]


def _find_next_pending_chunk(chunks: list[TuiChunkView]) -> TuiChunkView | None:
    """Return the next pending chunk in the current source."""

    for chunk in chunks:
        if chunk.status == "pending":
            return chunk
    return None


def _get_selected_chunk(dashboard: TuiDashboardView) -> TuiChunkView | None:
    """Return the selected chunk from the current dashboard."""

    return next(
        (
            chunk
            for chunk in dashboard.chunks
            if chunk.id == dashboard.selected_chunk_id
        ),
        None,
    )


def _render_dashboard(console: Console, dashboard: TuiDashboardView) -> None:
    """Render the interactive session dashboard."""

    console.print()
    console.print(_render_projects_table(dashboard))
    console.print(_render_sources_table(dashboard))
    console.print(_render_chunks_table(dashboard))
    console.print(_render_focus_panel(dashboard))
    if dashboard.tutorial is not None:
        console.print(_render_tutorial_panel(dashboard.tutorial))


def _render_tutorial_panel(tutorial: TutorialSessionView | None) -> Panel:
    """Render the current tutorial checklist or idle guidance."""

    if tutorial is None:
        raise ValueError("A tutorial panel requires an active tutorial session.")

    current_step = _resolve_current_tutorial_step(tutorial)
    current_step_title = (
        current_step.title if current_step is not None else tutorial.current_step
    )
    lines = [
        f"Status: {tutorial.status}",
        f"Step: {_tutorial_step_label(tutorial, current_step)}",
    ]
    if current_step is not None:
        lines.append(f"Command: {current_step.command}")
        lines.append(f"Goal: {current_step_title}")
        lines.extend(
            [
                "",
                "Do this:",
            ]
        )
        for index, action in enumerate(current_step.actions, start=1):
            lines.append(f"{index}. {action}")
        lines.extend(
            [
                "",
                f"Check: {current_step.success_condition}",
                f"Choice: {current_step.choice_hint}",
                f"Why: {current_step.why}",
                f"State: {current_step.detail}",
            ]
        )
    lines.append("")
    lines.append("Progress:")
    for step in tutorial.steps:
        marker = "[x]" if step.completed else "[ ]"
        prefix = (
            "->" if current_step is not None and step.key == current_step.key else "  "
        )
        lines.append(f"{prefix} {marker} {step.title}")
    return Panel("\n".join(lines), title="Tutorial")


def _tutorial_step_label(
    tutorial: TutorialSessionView,
    current_step: TutorialStepView | None,
) -> str:
    """Return the current tutorial step label."""

    if current_step is None:
        return "completed"
    current_index = tutorial.steps.index(current_step) + 1
    return f"{current_index}/{len(tutorial.steps)}"


def _resolve_current_tutorial_step(
    tutorial: TutorialSessionView,
) -> TutorialStepView | None:
    """Return the first incomplete tutorial step, or the final step if complete."""

    for step in tutorial.steps:
        if not step.completed:
            return step
    return tutorial.steps[-1] if tutorial.steps else None


def _render_projects_table(dashboard: TuiDashboardView) -> Table:
    """Render the projects list."""

    table = Table(title="Projects")
    table.add_column("#")
    table.add_column("Project")
    table.add_column("Sources", justify="right")
    table.add_column("Selected")
    for index, project in enumerate(dashboard.projects, start=1):
        table.add_row(
            str(index),
            project.name,
            str(project.source_count),
            "*" if project.id == dashboard.selected_project_id else "",
        )
    if not dashboard.projects:
        table.add_row("-", "No projects yet", "0", "")
    return table


def _render_sources_table(dashboard: TuiDashboardView) -> Table:
    """Render the sources list."""

    table = Table(title="Sources")
    table.add_column("#")
    table.add_column("Title")
    table.add_column("Transcript")
    table.add_column("Chunks", justify="right")
    table.add_column("Pending", justify="right")
    table.add_column("Candidates", justify="right")
    table.add_column("Selected")
    for index, source in enumerate(dashboard.sources, start=1):
        table.add_row(
            str(index),
            source.title,
            source.transcript_source or "-",
            str(source.chunk_count),
            str(source.pending_chunk_count),
            str(source.candidate_count),
            "*" if source.id == dashboard.selected_source_id else "",
        )
    if not dashboard.sources:
        table.add_row("-", "No sources in project", "-", "0", "0", "0", "")
    return table


def _render_chunks_table(dashboard: TuiDashboardView) -> Table:
    """Render the chunk list."""

    table = Table(title="Chunks")
    table.add_column("#")
    table.add_column("Chunk")
    table.add_column("Status")
    table.add_column("Chars", justify="right")
    table.add_column("Candidates", justify="right")
    table.add_column("Selected")
    for index, chunk in enumerate(dashboard.chunks, start=1):
        table.add_row(
            str(index),
            str(chunk.chunk_index + 1),
            chunk.status,
            str(chunk.char_count),
            str(chunk.candidate_count),
            "*" if chunk.id == dashboard.selected_chunk_id else "",
        )
    if not dashboard.chunks:
        table.add_row("-", "No chunks in source", "-", "0", "0", "")
    return table


def _render_focus_panel(dashboard: TuiDashboardView) -> Panel:
    """Render details for the selected chunk."""

    selected_chunk = _get_selected_chunk(dashboard)
    if selected_chunk is None:
        return Panel(
            "Select a source and chunk to inspect the current study text.",
            title="Focus",
        )

    lines = [
        f"Chunk {selected_chunk.chunk_index + 1}",
        f"Status: {selected_chunk.status}",
        (
            "Time: "
            f"{selected_chunk.start_seconds:.2f}s - "
            f"{selected_chunk.end_seconds:.2f}s"
        ),
        f"Candidates: {selected_chunk.candidate_count}",
        "Text:",
    ]
    lines.extend(_wrap_block(selected_chunk.text.strip(), indent="  "))
    review_context = dashboard.review_context
    if review_context is not None:
        lines.extend(_render_review_context_lines(review_context))
    lines.extend(
        _render_candidate_lines(dashboard.candidates, dashboard.publish_target)
    )

    return Panel("\n".join(lines), title="Focus")


def _render_review_context_lines(
    review_context: TuiReviewContextView,
) -> list[str]:
    """Render compact review context lines for the selected chunk."""

    lines = [f"Conversation: {review_context.conversation_id}"]
    if review_context.messages:
        latest_message = review_context.messages[-1]
        content = " ".join(latest_message.content.split())
        lines.append(f"Latest {latest_message.role}:")
        lines.extend(_wrap_block(content, indent="  "))
    return lines


def _render_candidate_lines(
    candidates: list[TuiCandidateView],
    publish_target: TuiPublishTargetView | None,
) -> list[str]:
    """Render candidate and publish-target lines for the selected chunk."""

    lines: list[str] = []
    if publish_target is not None:
        lines.append(
            "Publish Target: "
            f"{publish_target.deck_name} / {publish_target.note_type_name}"
        )
        tags = (
            ", ".join(publish_target.publish_tags)
            if publish_target.publish_tags
            else "-"
        )
        lines.append(f"Publish Tags: {tags}")
    if candidates:
        ready_count = sum(
            1 for candidate in candidates if candidate.status == "promoted"
        )
        published_count = sum(
            1
            for candidate in candidates
            if candidate.publication_status == "published"
            and candidate.anki_note_id is not None
        )
        lines.append(f"Chunk Candidates: {len(candidates)}")
        lines.append(
            f"Publish Queue: {ready_count} ready, {published_count} published locally"
        )
        for index, candidate in enumerate(candidates, start=1):
            candidate_line = (
                f"{candidate.candidate_type} | "
                f"{candidate.simplified or '-'} | "
                f"{candidate.english or '-'} | "
                f"{_describe_candidate_publish_state(candidate)}"
            )
            if candidate.anki_note_id is not None:
                candidate_line += f" | note {candidate.anki_note_id}"
            lines.extend(_wrap_indexed_row(index=index, body=candidate_line))
    return lines


def _describe_candidate_publish_state(candidate: TuiCandidateView) -> str:
    """Return a user-facing publish state label for one visible candidate."""

    if (
        candidate.publication_status == "published"
        and candidate.anki_note_id is not None
    ):
        return "published locally"
    if candidate.publication_status == "publishing":
        return "publishing"
    if candidate.status == "promoted":
        return "ready to publish"
    return candidate.status


def _wrap_block(text: str, *, indent: str) -> list[str]:
    """Wrap one free-form text block for the focus panel."""

    normalized = " ".join(text.split())
    if not normalized:
        return [f"{indent}-"]
    wrapped = wrap(
        normalized,
        width=FOCUS_WRAP_WIDTH,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [f"{indent}{line}" for line in wrapped]


def _wrap_indexed_row(*, index: int, body: str) -> list[str]:
    """Wrap one numbered row while keeping the index visible."""

    prefix = f"{index}. "
    wrapped = wrap(
        body,
        width=FOCUS_WRAP_WIDTH - len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return [prefix.rstrip()]
    lines = [f"{prefix}{wrapped[0]}"]
    continuation_prefix = " " * len(prefix)
    lines.extend(f"{continuation_prefix}{line}" for line in wrapped[1:])
    return lines
