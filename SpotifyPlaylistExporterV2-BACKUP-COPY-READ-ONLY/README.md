# SpotifyPlaylistExporterV2

A refactored, modular version of the original `spotify_playlist_exporter_gui_Kivy_v36.py` application.

## Project layout

```
SpotifyPlaylistExporterV2/
├── README.md
├── requirements.txt
└── src/
    └── spotify_playlist_exporter_v2/
        ├── __init__.py
        ├── __main__.py
        ├── app.py
        ├── config.py
        ├── logging_config.py
        ├── state.py
        ├── utils/
        │   └── platform_utils.py
        ├── caching/
        │   ├── __init__.py
        │   ├── persistent_cache.py
        │   └── analysis.py
        ├── services/
        │   └── reccobeats.py
        ├── auth/
        │   ├── __init__.py
        │   ├── http_handler.py
        │   └── login_screen.py
        ├── ui/
        │   ├── __init__.py
        │   ├── hover_manager.py
        │   ├── playlist_card.py
        │   ├── tracks_window.py
        │   └── layouts.py
        └── screens/
            ├── __init__.py
            └── main_screen.py
```

Run the application with:

## Running the Application

### Recommended: Using main.py
```bash
python main.py
```

### Alternative: Direct Module Execution
```bash
python -m spotify_playlist_exporter_v2
```

This preserves the full behavior of the original monolithic script while splitting the logic across smaller, purpose-specific modules.
