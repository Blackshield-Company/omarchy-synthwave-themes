# Omarchy Synthwave Themes

Three synthwave themes for [Omarchy](https://omarchy.org): neon palettes, procedurally rendered synthwave wallpapers, and matching configs. Every text color passes WCAG AA contrast, and CI checks that.

| Theme | Look |
|---|---|
| **Neon Horizon** | Hot pink and ice cyan on a midnight violet background |
| **Ocean Drive** | Ember orange and dusk magenta over a deep plum sky |
| **Chrome City** | Polished steel and electric cyan on a navy night |

![Neon Horizon](themes/neon-horizon/preview.png)
![Ocean Drive](themes/ocean-drive/preview.png)
![Chrome City](themes/chrome-city/preview.png)

## What's in a theme

`themes/<name>/` uses the Omarchy theme format, pinned to Omarchy `4.0.0.alpha` (basecamp/omarchy `b7e900c`, 2026-10-14):

- `colors.toml`: the palette. Omarchy uses it to render the Alacritty, Kitty, Ghostty, foot, Hyprland borders (gradient), btop, shell, mako and walker configs.
- `backgrounds/`: wallpapers at 2560x1440
- `neovim.lua`: a LazyVim colorscheme (tokyonight with the palette swapped in)
- `shell.lock.toml`: the lock screen
- `icons.theme`: a Yaru icon variant
- `preview.png`

`extras/<name>/` has standalone configs for older Omarchy releases (3.x, Waybar based) or plain Hyprland: `alacritty.toml`, `kitty.conf`, `ghostty.conf`, `hyprland.conf`, `waybar.css`, `mako.ini`, `walker.css` and `btop.theme`.

`wallpapers/<name>/<WxH>/` has every wallpaper at 1920x1080, 2560x1440, 3440x1440 and 5120x1440.

## Install

```bash
git clone https://github.com/Blackshield-Company/omarchy-synthwave-themes
cd omarchy-synthwave-themes
./install.sh list
./install.sh theme neon-horizon                    # copies to ~/.config/omarchy/themes and applies it
./install.sh theme ocean-drive --res 3440x1440      # use ultrawide wallpapers
./install.sh extras chrome-city                   # legacy configs -> ~/.config/omarchy-synthwave/chrome-city
```

After installing, switch themes from the Omarchy menu (Style > Theme) or with `omarchy-theme-set <name>`. To uninstall, delete `~/.config/omarchy/themes/<name>`.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/generate.py                     # configs from palettes/*.toml
.venv/bin/python scripts/generate.py --wallpapers --previews   # wallpapers + previews (Pillow + numpy)
./validate.sh                                            # layout, contrast, config syntax, shellcheck, luac
.venv/bin/python -m unittest discover -s tests
```

To change a theme, edit `palettes/<name>.toml` and run the generator. Never edit the generated files by hand, because CI fails when they drift from the palette.

## License

MIT for the code, configs and wallpapers. The wallpapers are drawn from scratch by `scripts/generate.py` (seeded, so every run gives the same images): a striped sun over wireframe mountains and a cyan grid (Neon Horizon), a coastal highway at sunset (Ocean Drive), and a neon chrome skyline over a purple grid (Chrome City). Ultrawide sizes show more of each scene instead of stretching it.
