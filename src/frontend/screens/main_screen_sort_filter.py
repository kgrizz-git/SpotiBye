"""Sort and filter helpers for MainScreen playlists."""

from __future__ import annotations

from typing import Any, Dict, List


def filter_playlists(
    playlists: List[Dict[str, Any]], search_query: str
) -> List[Dict[str, Any]]:
    """Get playlists filtered by the current search query.

    Args:
        playlists: List of playlist dictionaries to filter
        search_query: The text to search for

    Returns:
        Filtered list of playlists
    """
    if not search_query:
        return playlists.copy()

    # Compile search query once for better performance
    search_terms = [
        term.strip().lower() for term in search_query.split() if term.strip()
    ]
    if not search_terms:
        return playlists.copy()

    def matches_search(playlist: Dict[str, Any]) -> bool:
        playlist_name = playlist.get("name", "").lower()
        owner_name = playlist.get("owner", {}).get("display_name", "").lower()

        # Match all search terms (AND logic)
        return all(term in playlist_name or term in owner_name for term in search_terms)

    return [p for p in playlists if matches_search(p)]


def sort_playlists(
    playlists: List[Dict[str, Any]], sort_key: str, reverse: bool
) -> List[Dict[str, Any]]:
    """Sort playlists based on current sort key and direction.

    Args:
        playlists: List of playlist dictionaries to sort
        sort_key: The key to sort by ('default', 'name', 'tracks', 'owner')
        reverse: Whether to sort in reverse order

    Returns:
        Sorted list of playlists
    """
    if not playlists or sort_key == "default":
        return playlists

    def key_fn(pl):
        if sort_key == "name":
            return pl.get("name", "").lower()
        if sort_key == "tracks":
            return pl.get("tracks", {}).get("total", 0)
        if sort_key == "owner":
            return pl.get("owner", {}).get("display_name", "").lower()
        return ""

    return sorted(playlists, key=key_fn, reverse=reverse)
