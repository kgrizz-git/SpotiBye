# SpotiBye Configuration Options

## Choose a backend

On first launch, SpotiBye asks you to choose a backend before you sign in. It
does not silently connect to localhost or to a cloud service.

- **Localhost** is an explicit choice for a Worker you run locally.
- **Cloudflare Dev** and **Cloudflare Prod** appear only when your launcher has
  configured those endpoints.
- **Custom** lets you enter any valid `http://` or `https://` endpoint.

After you click **Continue**, SpotiBye remembers that URL in the private
`~/.spotibye_cache/backend_selection.json` file and restores it on later
launches. You can select **Change Backend** on the login screen at any time.
If you cancel the first chooser without selecting a URL, the app remains
unconfigured and will ask you to choose one before login.

## Optional launch configuration

Most users can use the chooser and need no configuration file. Developers and
advanced users can configure defaults in the environment of the app launcher.
The shipped `.desktop.env.example` file is a template, not an automatically
loaded file. Copy it to the ignored `.desktop.env.local` and source it from a
shell or configure equivalent values in an IDE launch profile.

```bash
cp .desktop.env.example .desktop.env.local
set -a && source .desktop.env.local && set +a
```

The endpoint variables are optional:

```bash
# Select this endpoint at startup when no saved choice exists.
SPOTIBYE_BACKEND_URL=https://your-default-backend.example

# Show these named choices in the selector.
SPOTIBYE_DEV_BACKEND_URL=https://your-dev-backend.example
SPOTIBYE_PRODUCTION_BACKEND_URL=https://your-prod-backend.example
```

Use your own endpoint values in `.desktop.env.local`; do not put credentials in
that file or commit it. See the [backend connectivity FAQ](faq-connectivity.md)
if a selected backend cannot be reached.
