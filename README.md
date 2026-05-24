# Forza Designer Radio Maker

Build a custom radio station for **Forza Horizon 6** from one of three sources, give it a name and logo, and hand the prepared bundle off to the FH6 Radio Tool for in-game replacement.

## Features

- **Spotify Radio** — paste a public Spotify playlist URL; track titles + artists are read from the playlist's embed page, then audio is fetched from the top YouTube match per track.
- **YouTube Radio** — paste a YouTube playlist or video URL; audio is downloaded directly.
- **Custom Station** — pick your own local audio files (mp3 / wav / flac / m4a / opus / aac / ogg / wma).
- Every station gets its **own name and logo** (or a branded placeholder is generated automatically).
- Audio is normalized to 16-bit 48 kHz stereo PCM WAV — the format the FH6 Radio Tool expects.
- One-click launch of the FH6 Radio Tool with:
  - the bundled **Fmod Bank Tools** auto-extracted and pre-configured,
  - the FH6 Radio Tool's UI forced to **English**,
  - the music-folder path copied to your clipboard ready to paste.
- `yt-dlp.exe` is fetched on first use from the official GitHub release into `%LOCALAPPDATA%\ForzaHorizonRadioMaker\bin\` so the app stays small and yt-dlp stays current.

## Install / run from source

Requires **Python 3.10+** on Windows.

```bat
setup_env.bat        :: one-time: create .venv and install deps
run.bat              :: launch the app
```

## Build the EXE

```bat
build_exe.bat
```

Produces `dist\ForzaHorizonRadioMaker.exe` (one-file, windowed). The Fmod Bank Tools zip in `forza_radio_maker\resources\` is bundled into the EXE and extracted to `%LOCALAPPDATA%\ForzaHorizonRadioMaker\fmod_bank_tools\` the first time you launch the FH6 Radio Tool from inside the app.

## How a build flow looks

1. Pick a mode (Spotify / YouTube / Custom).
2. Enter the URL or pick local files.
3. Type a station name and (optionally) pick a logo image.
4. Click **Build station**. yt-dlp is downloaded the first time; tracks are fetched and converted to WAV.
5. On the success screen click **Launch FH6 Radio Tool…** — the app:
   - extracts and registers Fmod Bank Tools on first run,
   - flips the FH6 Radio Tool's UI to English,
   - copies the prepared `music/` folder path to your clipboard,
   - launches the FH6 Radio Tool.
6. In the FH6 Radio Tool: paste the path into its **Music folder** field, select your target radio station slot, validate the audio, then **Generate Mod Output Package** or **One-Click Replace**.

## Project layout

```
ForzaDesignerRadioMaker\
  forza_radio_maker\
    app.py                 # QApplication bootstrap
    theme.py               # QSS reused from FH6 Radio Tool
    paths.py
    settings.py            # tiny JSON settings store (%LOCALAPPDATA%)
    ytdlp_runtime.py       # downloads & caches yt-dlp.exe on first use
    fh6_tool.py            # locate / launch / configure the FH6 Radio Tool
    station.py             # station metadata + logo normalization
    audio.py               # ffmpeg WAV conversion
    sources\
      youtube.py
      spotify.py
      custom.py
    ui\
      main_window.py       # wizard: mode -> configure -> build -> done
      workers.py
    resources\
      Fmod_Bank_Tools.zip  # extracted on first FH6 Radio Tool launch
  launcher.py              # PyInstaller entry point (absolute imports)
  build_exe.bat
  setup_env.bat
  run.bat
  requirements.txt
```

## Notes

- The FH6 Radio Tool is a separate program. The app auto-detects common install locations (Downloads / Documents / Desktop / Program Files) and remembers the path between sessions in `%LOCALAPPDATA%\ForzaHorizonRadioMaker\settings.json`.
- Spotify integration scrapes the public embed page — no API key needed, but the playlist must be public.
- yt-dlp updates frequently. If downloads start failing, delete `%LOCALAPPDATA%\ForzaHorizonRadioMaker\bin\yt-dlp.exe` and relaunch — the latest release will be fetched automatically.
- ffmpeg ships via the `imageio-ffmpeg` Python package; no separate install required.

## License

See [LICENSE](LICENSE). The bundled Fmod Bank Tools zip contains FMOD libraries that are subject to FMOD's own licensing terms (see `FMOD LICENSE.TXT` inside the extracted folder).
