-- Chrome City for LazyVim. Generated; do not edit by hand.
-- Uses tokyonight (bundled with Omarchy's LazyVim) with the palette overridden.
return {
  {
    "folke/tokyonight.nvim",
    priority = 1000,
    opts = {
      on_colors = function(c)
        c.bg = "#0b1120"
        c.bg_dark = "#080d1a"
        c.bg_float = "#080d1a"
        c.bg_sidebar = "#080d1a"
        c.bg_highlight = "#16203a"
        c.bg_visual = "#1d3358"
        c.fg = "#dfe8f5"
        c.fg_dark = "#c8d3e6"
        c.comment = "#8b9bb8"
        c.red = "#ff5f7e"
        c.green = "#6ee7a8"
        c.yellow = "#f5d76e"
        c.blue = "#6fa8ff"
        c.magenta = "#c792ff"
        c.purple = "#ddb8ff"
        c.cyan = "#22e3ff"
        c.orange = "#ffa25c"
        c.border_highlight = "#22e3ff"
      end,
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "tokyonight-storm",
    },
  },
}
