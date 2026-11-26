hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.config({
    general = {
        border_size = 1,
        col = {
            active_border = { colors = { "rgba(00e5ffee)", "rgba(ffb300ee)" }, angle = 45 },
            inactive_border = "rgba(26405a88)",
        },
    },
    decoration = {
        rounding = 16,
        blur = { enabled = true, size = 6, passes = 3, new_optimizations = true, ignore_opacity = true },
    },
    animations = { enabled = true },
    misc = { disable_hyprland_logo = true, disable_splash_rendering = true },
})

hl.animation({ leaf = "windowsIn", enabled = true, speed = 3, bezier = "default", style = "popin 88%" })
hl.window_rule({
    match = { class = ".+" },
    float = true,
    size = { "monitor_w * 0.44", "monitor_h * 0.76" },
    move = { "monitor_w * 0.52", "monitor_h * 0.12" },
    opacity = "0.92 0.88",
})

hl.on("hyprland.start", function()
    hl.exec_cmd('python "$JARVIS_ADA_DESKTOP"')
    hl.exec_cmd("jarvis-hud-preview")
    hl.exec_cmd("systemctl --user start jarvis-voice.service")
end)

local terminal = hl.dsp.exec_cmd("xdg-terminal-exec || foot")
local hud = "jarvis-hud-preview ipc call jarvis-hud-preview "
hl.bind("SUPER + Return", terminal)
hl.bind("SUPER + SHIFT + T", hl.dsp.exec_cmd("xdg-terminal-exec || foot"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + H", hl.dsp.workspace.toggle_special("vault"))
hl.bind("SUPER + SHIFT + H", hl.dsp.exec_cmd("hyprctl dispatch movetoworkspace special:vault"))
hl.bind("SUPER + L", hl.dsp.exec_cmd("jarvis-lock"))
hl.bind("SUPER + N", hl.dsp.exec_cmd(hud .. "toggleNotifications"))
hl.bind("SUPER + SPACE", hl.dsp.exec_cmd(hud .. "togglePalette"))
hl.bind("SUPER + SHIFT + C", hl.dsp.exec_cmd(hud .. "clear"))
hl.bind("SUPER + SHIFT + J", hl.dsp.exec_cmd("jarvis-hud-preview"))
hl.bind("SUPER + V", hl.dsp.exec_cmd("jarvis-voice-toggle voice"))
hl.bind("SUPER + D", hl.dsp.exec_cmd("jarvis-voice-toggle dictation"))
hl.bind("SUPER + SHIFT + V", hl.dsp.exec_cmd("jarvis-voice standby toggle"))
hl.bind("SUPER + Escape", hl.dsp.exec_cmd("jarvis-voice listen cancel"))
hl.bind("SUPER + SHIFT + Escape", hl.dsp.exit())
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
