# DeckZ

Free app by PINTAZ. Download: the [latest release](https://github.com/danish0440/deckz/releases/latest).

Based on DeckCraft by Storytold (ArtCraft), Apache-2.0. Changes by PINTAZ TECHNOLOGIES. See NOTICE, LICENSE-MIT and LICENSE-APACHE.

This repository follows upstream (`storytold/deckcraft`) every day through `.github/workflows/upstream-sync-z.yml`, which re-applies `.pintaz/rebrand.py`, runs the gates in `.pintaz/zgate.py` and, when they pass, merges and releases. Builds: `.github/workflows/release-z.yml` (unsigned Windows x64 MSI + portable zip, macOS universal DMG).
