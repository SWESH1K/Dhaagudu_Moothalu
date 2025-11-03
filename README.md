# Dhaagudu Moothalu

A fast, local-network multiplayer hide-and-seek game built with Pygame. One player becomes the seeker; the others are hidders who can disguise themselves as world objects. Hidders can emit a short whistle; the seeker tracks them down and tries to tag them before the round ends.

> Works on Windows. Python-based dev workflow; optional single-file EXE + Windows installer supported.


## Features

- Top-down 2D world with collisions and interactive objects (Tiled TMX map)
- LAN multiplayer with lightweight TCP + UDP discovery
- Host directly from the client or join an existing server
- Hidders can transform into nearby objects; seeker can tag hidders
- In-game ambience and spatialized sound cues for the whistle


## Controls

- Move: Arrow keys (Up/Down/Left/Right)
- Interact / Transform / Catch: X
  - Hidders: stand facing an object and press X to disguise; press X again to revert
  - Seeker: press X near a player in front of you to catch/freeze them
- Whistle (Hidders only): Y

Notes:
- The seeker is always player index 0 for a round; all other connected players are hidders.
- Caught hidders are frozen and cannot move until the round ends.


## Requirements

- Python 3.10+ (3.11+ recommended)
- Windows 10/11 (tested)
- Packages (installed via `requirements.txt`):
  - pygame==2.6.1
  - pygame-ce==2.5.6
  - PyTMX==3.32


## Quick Start (development)

From a PowerShell terminal in the repo root:

```powershell
# 1) (Optional) create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run the game (client with main menu)
python .\client.py
```

From the main menu you can:
- Host: pick port and player count; a background server is launched automatically and you connect to it.
- Join: discover servers on your LAN or enter an IP manually.
- Settings: tweak resolution and network defaults (also see `settings.py`).


## Running client and server explicitly

You can also run the server yourself and point clients to it.

- Start the server (bind to all interfaces, advertise via UDP discovery):

```powershell
python .\server.py --auto-ip --port 5555 --num-players 2
```

- Join from another PC on the same network:
  - Use the Join menu to pick a discovered server, or
  - Enter the server IP manually in the Join menu, or
  - Edit `settings.py` and set `server = 'YOUR.SERVER.IP'` and `port = 5555`.

Firewall tip: allow the Python process for both TCP port (e.g., 5555) and UDP discovery port (`DISCOVERY_PORT` in `settings.py`, default 5556).


## Building a Windows EXE / Installer

See `README_INSTALLER.md` for a one-command PowerShell build that:
- packages the game into a single-file EXE with PyInstaller, and
- optionally compiles an Inno Setup installer.

File references:
- Script: `build_scripts/build_installer.ps1`
- Inno Setup definition: `installer/installer.iss`


## Project structure (high level)

```
client.py            # Game entry point + menu (Host/Join/Settings) and main loop
server.py            # TCP game server + UDP discovery responder
network.py           # TCP client and LAN discovery utilities
settings.py          # Window size, FPS, server/port, player count, discovery ports

controllers/
  input.py           # Keyboard input handling (X to interact/catch, Y to whistle)

core/
  contracts.py       # Small interfaces / datamodels for game services

data/
  maps/world.tmx     # Tiled map
  tilesets/, graphics/objects/tilesets/  # Map resources

images/              # Spritesheets (player/seekers, enemies, objects, logos)
sounds/              # Audio (walking, whistle, ambience)

renderers/
  world.py           # World rendering (map, objects)
  hud.py             # HUD rendering (round timer, messages)

services/
  audio.py           # Pygame audio helpers (whistle + ambient)
  networking.py      # Adapter to the legacy TCP client
  timer.py           # Round timer service

server_core/
  protocol.py        # Parse/build messages
  broadcaster.py     # Broadcast updates to clients
  session.py         # Authoritative session/state container
  rounds.py          # Round management (start, end, win conditions)

net/
  sync.py            # JSON/CSV sync helpers for state exchange

util/
  resource_path.py   # Path helper for dev and PyInstaller builds

installer/           # Inno Setup script
build_scripts/       # PowerShell build for EXE/installer
```


## How to play (short)

- Host or Join from the main menu.
- If you Host, you are the server owner and will also join as a player. The first player in a round is the seeker.
- Hidders should blend in by transforming into objects. Keep moving carefully–the whistle helps your teammates coordinate, but it also gives the seeker audio clues.
- The round ends when the seeker freezes all hidders or when the timer expires.


## Contributing

Contributions are very welcome! Please follow these guidelines to keep the project healthy and fun:

1) Fork and branch
- Fork the repo and create a feature branch from `main`:
  - `feature/menu-polish`, `fix/whistle-pan`, `docs/readme`, etc.

2) Dev environment
- Windows + Python 3.10/3.11 recommended.
- Install deps: `pip install -r requirements.txt`.
- Run: `python .\client.py`.

3) Code style
- Prefer PEP8; add type hints where it clarifies intent.
- Keep changes focused and small; include comments for tricky logic.
- Assets: place new images under `images/` (PNG with alpha), new sounds under `sounds/`.
- Maps: edit `data/maps/world.tmx` with Tiled; include updated tilesets if needed.

4) Testing your change
- Sanity check by hosting a game locally and joining from a second client (can be on the same PC).
- Try both roles (seeker/hidder). Verify object transforms and catch logic with the X key.

5) Submitting
- Open a Pull Request against `main` with a concise description, before/after screenshots or short clips when UI/gameplay changes.
- Link any related issues; call out breaking changes.

6) Networking notes
- The server is authoritative for “caught/frozen” and round wins.
- Reuse helpers in `net/sync.py` and `server_core/protocol.py` when changing payloads.
- If you evolve the message format, keep backward compatibility or update both sides together.


## Troubleshooting

- Pygame mixer errors: ensure an audio device is available; the game will still run but sounds may be disabled.
- Can’t join a host: verify the host shows up in Join > Refresh; otherwise enter the IP manually. Check Windows Firewall for TCP port (e.g., 5555) and UDP discovery port (default 5556).
- Black screen or missing assets: confirm you run from the repo root so relative paths to `data/` and `images/` resolve.


## License

No license has been declared yet. If you want to use this code in your project, please open an issue so we can clarify terms.


## Credits

- Built with love and Pygame. Tiled maps via PyTMX.
- Game, code, and assets © their respective authors.
