-- Neon Contract for LazyVim. Generated; do not edit by hand.
-- Uses tokyonight (bundled with Omarchy's LazyVim) with the palette overridden.
return {
  {
    "folke/tokyonight.nvim",
    priority = 1000,
    opts = {
      on_colors = function(c)
        c.bg = "#0f0b1f"
        c.bg_dark = "#0b0818"
        c.bg_float = "#0b0818"
        c.bg_sidebar = "#0b0818"
        c.bg_highlight = "#1c1535"
        c.bg_visual = "#3b1d5e"
        c.fg = "#f1e9ff"
        c.fg_dark = "#d9cff0"
        c.comment = "#9a8cc4"
        c.red = "#ff4f7b"
        c.green = "#72f1b8"
        c.yellow = "#fede5d"
        c.blue = "#4fb3ff"
        c.magenta = "#ff6ad5"
        c.purple = "#ff9ae3"
        c.cyan = "#36f9f6"
        c.orange = "#ff9e4f"
        c.border_highlight = "#ff4fc4"
      end,
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "tokyonight-night",
    },
  },
}
