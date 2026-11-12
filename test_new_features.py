"""Tests for favorites, usage tracking, editing-before-copy, search ranking,
change detection, new prompts, tray favorites, and crash reporting."""

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import pytest

from app_state import AppState
from prompt_manager import Prompt, PromptManager


def _write_config(path: Path, categories: list, settings: dict | None = None) -> Path:
    data = {
        "settings": settings or {"auto_close": False, "show_notifications": False},
        "categories": categories,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _bump_mtime(path: Path) -> None:
    """Make sure a rewritten file gets a different mtime on coarse clocks."""
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


@pytest.fixture()
def manager(tmp_path: Path) -> PromptManager:
    (tmp_path / "prompts" / "git").mkdir(parents=True)
    (tmp_path / "prompts" / "git" / "branch.md").write_text("Make a branch", encoding="utf-8")
    _write_config(tmp_path / "prompts.json", [
        {"name": "Meetings", "prompts": [
            {"title": "Summarize meeting", "text": "Summarize with action items"},
            {"title": "Clean transcript", "text": "Fix grammar in the meeting transcript"},
            {"title": "Action items only", "text": "List them"},
        ]},
        {"name": "Git", "prompts": [
            {"title": "Create branch", "file": "prompts/git/branch.md", "pinned": True},
        ]},
    ])
    return PromptManager(config_path=tmp_path / "prompts.json")


# ---------------------------------------------------------------------------
# PromptManager
# ---------------------------------------------------------------------------

class TestSearchRanking:
    def test_title_matches_rank_above_body_matches(self, manager):
        titles = [p.title for p in manager.search("action items")]
        # Title contains phrase beats body-only match
        assert titles.index("Action items only") < titles.index("Summarize meeting")

    def test_all_words_must_match_in_any_order(self, manager):
        titles = [p.title for p in manager.search("transcript grammar")]
        assert titles == ["Clean transcript"]

    def test_popularity_breaks_ties(self, manager):
        # Both are body-only matches for "meeting"? Summarize has it in title.
        base = [p.title for p in manager.search("the")]
        popular = {"Meetings::Clean transcript": 10}
        ranked = [p.title for p in manager.search("the", popular)]
        assert set(base) == set(ranked)
        assert ranked[0] == "Clean transcript"

    def test_empty_query_returns_everything(self, manager):
        assert len(manager.search("  ")) == 4


class TestChangeDetection:
    def test_no_reload_when_unchanged(self, manager):
        assert manager.reload_if_changed() is False

    def test_reload_when_referenced_file_changes(self, manager, tmp_path):
        md = tmp_path / "prompts" / "git" / "branch.md"
        md.write_text("Make a NEW branch", encoding="utf-8")
        _bump_mtime(md)
        assert manager.reload_if_changed() is True
        assert manager.find_by_key("Git::Create branch").text == "Make a NEW branch"

    def test_reload_when_config_changes(self, manager, tmp_path):
        cfg = tmp_path / "prompts.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["categories"][0]["prompts"].append({"title": "New", "text": "x"})
        cfg.write_text(json.dumps(data), encoding="utf-8")
        _bump_mtime(cfg)
        assert manager.reload_if_changed() is True
        assert manager.find_by_key("Meetings::New") is not None


class TestFavorites:
    def test_pinned_loaded_from_config(self, manager):
        assert [p.title for p in manager.get_pinned_prompts()] == ["Create branch"]

    def test_set_pinned_persists(self, manager, tmp_path):
        prompt = manager.find_by_key("Meetings::Clean transcript")
        assert manager.set_pinned(prompt, True) is True
        reloaded = PromptManager(config_path=tmp_path / "prompts.json")
        assert {p.title for p in reloaded.get_pinned_prompts()} == {"Create branch", "Clean transcript"}

    def test_unpin_removes_key(self, manager, tmp_path):
        prompt = manager.find_by_key("Git::Create branch")
        assert manager.set_pinned(prompt, False) is True
        raw = json.loads((tmp_path / "prompts.json").read_text(encoding="utf-8"))
        assert "pinned" not in raw["categories"][1]["prompts"][0]

    def test_set_pinned_refuses_when_file_changed_underneath(self, manager, tmp_path):
        prompt = manager.find_by_key("Meetings::Clean transcript")
        cfg = tmp_path / "prompts.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["categories"][0]["prompts"].insert(0, {"title": "Inserted", "text": "x"})
        cfg.write_text(json.dumps(data), encoding="utf-8")
        assert manager.set_pinned(prompt, True) is False

    def test_builtin_prompt_cannot_be_pinned(self, manager):
        assert manager.set_pinned(Prompt("t", "x", "Built-in Workflow"), True) is False


class TestAddPrompt:
    def test_add_to_existing_category_creates_md_file(self, manager, tmp_path):
        prompt = manager.add_prompt("Git", "Rebase onto main!", "Rebase it")
        assert prompt.file == "prompts/git/rebase-onto-main.md"
        assert (tmp_path / prompt.file).read_text(encoding="utf-8") == "Rebase it"
        assert manager.find_by_key("Git::Rebase onto main!").text == "Rebase it"

    def test_add_creates_new_category(self, manager):
        prompt = manager.add_prompt("Writing", "Polish", "Polish this")
        assert "Writing" in manager.user_categories
        assert prompt.category == "Writing"

    def test_duplicate_title_gets_unique_file(self, manager):
        a = manager.add_prompt("Git", "Same", "one")
        b = manager.add_prompt("Git", "Same", "two")
        assert a.file != b.file
        assert len([p for p in manager.get_prompts_by_category("Git") if p.title == "Same"]) == 2

    @pytest.mark.parametrize("category,title,text", [
        ("", "t", "x"), ("c", " ", "x"), ("c", "t", "  "), ("Built-in Workflow", "t", "x"),
    ])
    def test_validation(self, manager, category, title, text):
        with pytest.raises(ValueError):
            manager.add_prompt(category, title, text)

    def test_source_paths(self, manager, tmp_path):
        assert manager.get_source_path(None) == tmp_path / "prompts.json"
        assert manager.get_source_path(manager.find_by_key("Git::Create branch")) == (
            tmp_path / "prompts/git/branch.md"
        )
        assert manager.get_source_path(manager.find_by_key("Meetings::Clean transcript")) == (
            tmp_path / "prompts.json"
        )


# ---------------------------------------------------------------------------
# AppState
# ---------------------------------------------------------------------------

class TestAppState:
    def test_usage_roundtrip_and_ordering(self, tmp_path):
        state = AppState(path=tmp_path / "s.json")
        for _ in range(3):
            state.record_use("a")
        state.record_use("b")
        reloaded = AppState(path=tmp_path / "s.json")
        assert reloaded.use_count("a") == 3
        assert reloaded.most_used() == ["a", "b"]

    def test_ui_roundtrip(self, tmp_path):
        AppState(path=tmp_path / "s.json").set_ui("geometry", "600x700+10+20")
        assert AppState(path=tmp_path / "s.json").get_ui("geometry") == "600x700+10+20"

    def test_corrupt_file_starts_fresh(self, tmp_path):
        (tmp_path / "s.json").write_text("{not json", encoding="utf-8")
        state = AppState(path=tmp_path / "s.json")
        assert state.most_used() == []

    def test_in_memory_never_writes(self, tmp_path):
        state = AppState(path=tmp_path / "s.json", persist=False)
        state.record_use("a")
        assert not (tmp_path / "s.json").exists()


# ---------------------------------------------------------------------------
# Tray favorites + notifications
# ---------------------------------------------------------------------------

class TestTrayFavorites:
    def test_menu_lists_favorites_and_escapes_ampersand(self):
        from tray_manager import TrayManager

        tm = TrayManager(Mock(), Mock(), get_favorites=lambda: [("k", "Q&A prep")])
        texts = [str(item.text) for item in tm._create_menu()]
        assert "   Q&&A prep" in texts
        assert "Open" in texts and "Quit" in texts

    def test_menu_without_favorites_is_plain(self):
        from tray_manager import TrayManager

        tm = TrayManager(Mock(), Mock(), get_favorites=lambda: [])
        assert [str(i.text) for i in tm._create_menu() if not str(i.text).startswith("- ")] == ["Open", "Quit"]

    def test_favorite_click_reports_key(self):
        from tray_manager import TrayManager

        on_favorite = Mock()
        tm = TrayManager(Mock(), Mock(), get_favorites=lambda: [("Git::B", "B")],
                         on_favorite=on_favorite)
        item = next(i for i in tm._create_menu() if str(i.text).strip() == "B")
        item(Mock())
        on_favorite.assert_called_once_with("Git::B")

    def test_broken_favorites_provider_does_not_break_menu(self):
        from tray_manager import TrayManager

        def boom():
            raise RuntimeError("x")

        tm = TrayManager(Mock(), Mock(), get_favorites=boom)
        assert "Open" in [str(i.text) for i in tm._create_menu()]

    def test_notify_uses_icon(self):
        from tray_manager import TrayManager

        tm = TrayManager(Mock(), Mock())
        tm.icon = Mock(HAS_NOTIFICATION=True)
        tm.notify("OrgPrompt", "hi")
        tm.icon.notify.assert_called_once_with("hi", "OrgPrompt")

    def test_notify_without_icon_is_noop(self):
        from tray_manager import TrayManager

        TrayManager(Mock(), Mock()).notify("t", "m")


# ---------------------------------------------------------------------------
# Crash reporting
# ---------------------------------------------------------------------------

class TestExceptionHooks:
    def test_thread_exceptions_are_logged(self):
        from logging_config import install_exception_hooks

        saved = (sys.excepthook, threading.excepthook)
        logger = Mock()
        try:
            install_exception_hooks(logger)

            def boom():
                raise ValueError("bad")

            t = threading.Thread(target=boom, name="worker")
            t.start()
            t.join()
            assert logger.critical.called
            assert "worker" in logger.critical.call_args[0]
        finally:
            sys.excepthook, threading.excepthook = saved

    def test_sys_excepthook_logs(self):
        from logging_config import install_exception_hooks

        saved = (sys.excepthook, threading.excepthook)
        logger = Mock()
        try:
            install_exception_hooks(logger)
            try:
                raise RuntimeError("x")
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
            logger.critical.assert_called_once()
        finally:
            sys.excepthook, threading.excepthook = saved


# ---------------------------------------------------------------------------
# PromptWindow (real Tk, hidden)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture()
def copied(monkeypatch):
    calls = []

    def fake_copy(text, notification=True, notifier=None, message=""):
        calls.append(text)
        return True

    monkeypatch.setattr("prompt_window.copy_with_notification", fake_copy)
    return calls


@pytest.fixture()
def window(tk_root, manager, tmp_path):
    from prompt_window import PromptWindow

    state = AppState(path=tmp_path / "state.json")
    pw = PromptWindow(prompt_manager=manager, state=state)
    pw.show()
    yield pw
    pw.destroy()


def _iid_for_title(pw, title):
    return next(i for i, p in pw._items.items() if p.title == title)


def _section_labels(pw):
    return [pw.tree.item(i, "text") for i in pw._sections]


class TestEditBeforeCopy:
    def test_copy_uses_edited_text_and_keeps_original(self, window, copied, manager):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Summarize meeting"))
        window.preview_text.insert(tk.END, " for Project X")
        window._update_edit_state()

        assert str(window.reset_btn.cget("state")) == tk.NORMAL
        window._select_prompt()

        assert copied == ["Summarize with action items for Project X"]
        assert manager.find_by_key("Meetings::Summarize meeting").text == "Summarize with action items"
        assert window.state.use_count("Meetings::Summarize meeting") == 1

    def test_reset_restores_original(self, window):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        window.preview_text.insert("1.0", "XXX ")
        window._reset_edits()
        assert window._current_text() == "Fix grammar in the meeting transcript"
        assert not window._is_dirty()

    def test_selecting_another_prompt_replaces_edits(self, window):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        window.preview_text.insert("1.0", "XXX ")
        window._select_item(_iid_for_title(window, "Summarize meeting"))
        assert window._current_text() == "Summarize with action items"

    def test_list_rebuild_keeps_edits(self, window):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        window.preview_text.insert("1.0", "XXX ")
        window._refresh_list()
        window._on_tree_select()
        assert window._current_text().startswith("XXX ")

    def test_ctrl_return_in_preview_is_swallowed(self, window, copied):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        assert window._on_ctrl_return() == "break"
        assert copied == ["Fix grammar in the meeting transcript"]

    def test_nothing_selected_does_not_copy(self, window, copied):
        window._select_prompt()
        assert copied == []


class TestSectionsAndFavorites:
    def test_favorites_first_and_categories_collapsed_by_default(self, window):
        labels = _section_labels(window)
        assert labels[0].startswith("▼ ★ Favorites (1)")
        assert any(lbl.startswith("▶ Meetings (3)") for lbl in labels)
        assert [p.title for p in window._items.values()] == ["Create branch"]

    def test_frequent_section_appears_after_use(self, window, copied):
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        window._select_prompt()
        window._refresh_list()
        assert any("Frequently Used (1)" in lbl for lbl in _section_labels(window))

    def test_expanded_state_is_persisted(self, window, tk_root, manager):
        from prompt_window import PromptWindow

        window._toggle_section("Git", True)
        again = PromptWindow(prompt_manager=manager, state=window.state)
        assert "Git" in again._expanded

    def test_toggle_pin_adds_to_favorites(self, window, manager):
        window._toggle_section("Meetings", True)
        window._toggle_pin(manager.find_by_key("Meetings::Clean transcript"))
        assert _section_labels(window)[0].startswith("▼ ★ Favorites (2)")

    def test_duplicate_titles_do_not_crash(self, window, manager):
        manager.add_prompt("Meetings", "Clean transcript", "second copy")
        window._expanded.add("Meetings")
        window._refresh_list()
        dupes = [p for p in window._items.values() if p.title == "Clean transcript"]
        assert len(dupes) == 2


class TestKeyboardAndSearch:
    def test_enter_in_search_copies_top_match(self, window, copied):
        window.search_var.set("action items")
        window._on_search_return()
        assert copied == ["List them"]

    def test_enter_with_no_matches(self, window, copied):
        window.search_var.set("zzzz")
        window._on_search_return()
        assert copied == []
        assert window.status_var.get() == "No matching prompts"

    def test_down_moves_into_results(self, window):
        window.search_var.set("transcript")
        window._on_search_down()
        assert window.selected_prompt.title == "Clean transcript"

    def test_search_is_debounced(self, window):
        window._refresh_list = Mock(wraps=window._refresh_list)
        window.search_var.set("a")
        window.search_var.set("ab")
        assert window._refresh_list.call_count == 0
        window._flush_search()
        assert window._refresh_list.call_count == 1


class TestPersistentWindow:
    def test_close_hides_and_show_reuses_and_resets(self, window):
        root = window.root
        window.search_var.set("branch")
        window._close()
        assert root.state() == "withdrawn"
        window.show()
        assert window.root is root
        assert window.search_var.get() == ""

    def test_show_picks_up_file_changes(self, window, tmp_path):
        window._close()
        md = tmp_path / "prompts" / "git" / "branch.md"
        md.write_text("Changed", encoding="utf-8")
        _bump_mtime(md)
        window.show()
        assert window.prompt_manager.find_by_key("Git::Create branch").text == "Changed"

    def test_geometry_saved_and_restored(self, tk_root, manager, tmp_path):
        from prompt_window import PromptWindow

        state = AppState(path=tmp_path / "g.json")
        state.set_ui("geometry", "600x700+40+50")
        pw = PromptWindow(prompt_manager=manager, state=state)
        pw.show()
        pw.root.update_idletasks()
        assert pw.root.geometry().startswith("600x700")
        pw._close()
        assert state.get_ui("geometry").startswith("600x700")
        pw.destroy()

    def test_offscreen_geometry_is_recentered(self, tk_root, manager, tmp_path):
        from prompt_window import PromptWindow

        state = AppState(path=tmp_path / "g.json")
        state.set_ui("geometry", "600x700+99999+99999")
        pw = PromptWindow(prompt_manager=manager, state=state)
        pw.show()
        pw.root.update_idletasks()
        x = pw.root.winfo_x()
        assert x < pw.root.winfo_screenwidth()
        pw.destroy()


class TestSaveAsNew:
    def test_save_as_new_prefills_dialog(self, window, monkeypatch):
        captured = {}

        class FakeDialog:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def show(self):
                pass

        monkeypatch.setattr("new_prompt_dialog.NewPromptDialog", FakeDialog)
        window._toggle_section("Meetings", True)
        window._select_item(_iid_for_title(window, "Clean transcript"))
        window.preview_text.insert("1.0", "Edited: ")
        window._save_as_new()
        assert captured["text"] == "Edited: Fix grammar in the meeting transcript"
        assert captured["category"] == "Meetings"
        assert captured["title"] == "Clean transcript (copy)"

    def test_dialog_saves_prompt(self, tk_root, manager):
        from new_prompt_dialog import NewPromptDialog

        saved = []
        dlg = NewPromptDialog(parent=tk_root, prompt_manager=manager, on_saved=saved.append,
                              title="Fresh", category="Writing", text="Write well")
        dlg._build()
        dlg._on_save()
        assert saved and saved[0].title == "Fresh"
        assert dlg.dialog is None
