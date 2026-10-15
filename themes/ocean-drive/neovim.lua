-- Ocean Drive for LazyVim. Generated; do not edit by hand.
-- Uses tokyonight (bundled with Omarchy's LazyVim) with the palette overridden.
return {
  {
    "folke/tokyonight.nvim",
    priority = 1000,
    opts = {
      on_colors = function(c)
        c.bg = "#1a0f24"
        c.bg_dark = "#150b1e"
        c.bg_float = "#150b1e"
        c.bg_sidebar = "#150b1e"
        c.bg_highlight = "#2a1836"
        c.bg_visual = "#4a1f3d"
        c.fg = "#ffe9dc"
        c.fg_dark = "#eed7cf"
        c.comment = "#a98aa6"
        c.red = "#ff5c7a"
        c.green = "#8ee6a6"
        c.yellow = "#ffc85a"
        c.blue = "#8aa8ff"
        c.magenta = "#e07bff"
        c.purple = "#eeaaff"
        c.cyan = "#62e3dc"
        c.orange = "#ff8a3d"
        c.border_highlight = "#ff8a3d"
      end,
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "tokyonight-moon",
    },
  },
}
