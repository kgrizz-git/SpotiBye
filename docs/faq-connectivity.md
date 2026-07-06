# SpotiBye Connectivity FAQ

## General Questions

**Q: Does SpotiBye work offline?**
A: No, SpotiBye requires an internet connection to access Spotify data and perform analysis.

**Q: What kind of internet connection do I need?**
A: Any stable internet connection works. Faster connections improve loading times for large playlists.

**Q: Can I use SpotiBye on mobile data?**
A: Yes, but be aware that large playlists may use significant data.

## Authentication Issues

**Q: Why do I need to login with Spotify?**
A: SpotiBye needs permission to access your playlist data for analysis and export.

**Q: Is my Spotify password stored anywhere?**
A: No, your password never leaves Spotify's secure login page.

**Q: How often do I need to login?**
A: Sessions last 1 hour of inactivity. You'll need to login again after that.

**Q: What is Spotify's 6-month refresh token expiration policy?**
A: Starting on July 20, 2026, Spotify enforces a security policy where user authorizations (refresh tokens) expire exactly 6 months from the date of the original authorization, regardless of user activity. When this happens, SpotiBye will automatically redirect you to the login screen and show a message: *"Your Spotify session has expired. Please sign in again."* You simply need to click "Log In" in the app and sign in/authorize again via your web browser to renew the 6-month access. For more details, see [Spotify's Token Refresh Documentation](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens) and the [Developer Blog Announcement](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration).

**Q: What if I deny permissions?**
A: SpotiBye won't be able to access your playlists. You'll need to re-authorize.

## Performance Questions

**Q: Why do large playlists take so long to load?**
A: Large playlists (>1000 tracks) require more data processing. This is normal.

**Q: Can I speed up loading times?**
A: Use a faster internet connection and try loading smaller playlists first.

**Q: Why does SpotiBye sometimes feel slow?**
A: Network latency, large playlists, or backend processing can affect speed.

## Network Problems

**Q: What if I'm behind a corporate firewall?**
A: Some firewalls block access. Contact your IT administrator if needed.

**Q: Does SpotiBye work with VPNs?**
A: Usually yes, but some VPN configurations may cause issues.

**Q: What if my internet is unstable?**
A: SpotiBye will retry failed requests, but very unstable connections may not work well.

## Error Messages

**Q: "Unable to connect to backend"**
A: Check your internet connection and try again in a few minutes.

**Q: "Request timed out"**
A: Your connection is too slow. Try again with better internet.

**Q: "Authentication failed"**
A: Your session expired. Simply login again to continue.
