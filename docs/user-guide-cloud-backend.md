# SpotiBye User Guide - Cloud Backend Version

## Overview

SpotiBye now uses a cloud-based backend for improved performance and reliability. This guide explains how to use the updated application.

## What's Changed

- **Cloud Processing**: All Spotify API calls now go through our secure cloud backend
- **Faster Performance**: Optimized caching and processing in the cloud
- **Better Reliability**: Improved error handling and retry mechanisms
- **Enhanced Security**: Your Spotify credentials never leave your device

## Getting Started

### 1. Installation

Download and install SpotiBye from the official distribution channels.

### 2. First Launch

When you first launch SpotiBye, you'll need to authenticate with Spotify:

1. Click "Login with Spotify"
2. Your browser will open to the Spotify authorization page
3. Approve the requested permissions
4. Return to SpotiBye - you're now logged in!

## Using SpotiBye

### Loading Your Playlists

1. After login, your playlists will automatically load
2. Large playlists may take a few moments to load
3. Loading progress is shown in the status bar

### Analyzing Playlists

1. Select any playlist from your library
2. Click "Analyze" to see detailed statistics
3. Analysis happens in the cloud for faster processing

### Exporting Playlists

1. Select a playlist you want to export
2. Choose your export format (CSV, JSON, etc.)
3. Click "Export" and choose a save location
4. Progress is shown during export

## Network Requirements

SpotiBye requires an internet connection to:
- Authenticate with Spotify
- Load your playlists and tracks
- Perform playlist analysis
- Export your data

## Performance Tips

- **Large Playlists**: Playlists with 1000+ tracks may take longer to process
- **Multiple Playlists**: You can work with multiple playlists simultaneously
- **Caching**: Frequently accessed data is cached for faster loading
