#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <dirent.h>

/**
 * omarchy_ctrl — Sub-millisecond C++ Native Controller for Omarchy & Hyprland.
 *
 * Direct Unix Domain Socket IPC to Hyprland for zero-overhead window/workspace management,
 * and high-speed process execution for Omarchy theme/toggle/service actuators.
 *
 * Usage:
 *   omarchy_ctrl hypr <command> [args...]
 *   omarchy_ctrl theme <action> [args...]
 *   omarchy_ctrl toggle <flag> [args...]
 *   omarchy_ctrl restart <service>
 *   omarchy_ctrl capture <type>
 *   omarchy_ctrl launch <app> [args...]
 *   omarchy_ctrl system <action>
 *   omarchy_ctrl osd <message> [icon]
 *   omarchy_ctrl raw <omarchy-args...>
 */

static std::string escape_json(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 16);
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\b') out += "\\b";
        else if (c == '\f') out += "\\f";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (static_cast<unsigned char>(c) < 0x20) {
            char buf[8];
            snprintf(buf, sizeof(buf), "\\u%04x", c);
            out += buf;
        } else {
            out += c;
        }
    }
    return out;
}

// ── Hyprland Direct Socket IPC ─────────────────────────────────────────────

static std::string get_hyprland_socket_path() {
    const char* xdg_runtime = getenv("XDG_RUNTIME_DIR");
    std::string runtime_dir = xdg_runtime ? xdg_runtime : ("/run/user/" + std::to_string(getuid()));

    const char* sig = getenv("HYPRLAND_INSTANCE_SIGNATURE");
    if (sig && strlen(sig) > 0) {
        return runtime_dir + "/hypr/" + sig + "/.socket.sock";
    }

    // Auto-discover if env var is missing
    std::string hypr_base = runtime_dir + "/hypr";
    DIR* dir = opendir(hypr_base.c_str());
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != nullptr) {
            if (entry->d_name[0] != '.') {
                std::string cand = hypr_base + "/" + entry->d_name + "/.socket.sock";
                if (access(cand.c_str(), R_OK | W_OK) == 0) {
                    closedir(dir);
                    return cand;
                }
            }
        }
        closedir(dir);
    }
    return "";
}

static bool send_hyprland_cmd(const std::string& cmd, std::string& response) {
    std::string sock_path = get_hyprland_socket_path();
    if (sock_path.empty()) {
        response = "Hyprland socket not found";
        return false;
    }

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        response = "Socket creation failed";
        return false;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sock_path.c_str(), sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        response = "Connect to Hyprland socket failed";
        return false;
    }

    std::string to_send = cmd + "\n";
    if (write(fd, to_send.c_str(), to_send.length()) < 0) {
        close(fd);
        response = "Write to Hyprland socket failed";
        return false;
    }

    char buffer[4096];
    std::string res;
    ssize_t bytes;
    while ((bytes = read(fd, buffer, sizeof(buffer) - 1)) > 0) {
        buffer[bytes] = '\0';
        res += buffer;
    }
    close(fd);

    response = res;
    return (res.find("error:") == std::string::npos);
}

// ── Process Runner ─────────────────────────────────────────────────────────

static bool run_cmd_capture(const std::vector<std::string>& cmd_args, std::string& output, int timeout_sec = 5) {
    (void)timeout_sec;
    int pipefd[2];
    if (pipe(pipefd) < 0) {
        output = "Pipe failed";
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(pipefd[0]);
        close(pipefd[1]);
        output = "Fork failed";
        return false;
    }

    if (pid == 0) {
        // Child
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);

        std::vector<char*> argv;
        for (const auto& arg : cmd_args) {
            argv.push_back(const_cast<char*>(arg.c_str()));
        }
        argv.push_back(nullptr);

        execvp(argv[0], argv.data());
        _exit(127);
    }

    // Parent
    close(pipefd[1]);
    char buf[1024];
    output.clear();
    ssize_t n;
    while ((n = read(pipefd[0], buf, sizeof(buf) - 1)) > 0) {
        buf[n] = '\0';
        output += buf;
    }
    close(pipefd[0]);

    int status;
    waitpid(pid, &status, 0);
    return WIFEXITED(status) && (WEXITSTATUS(status) == 0);
}

// ── Main Controller ────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    auto t0 = std::chrono::high_resolution_clock::now();

    if (argc < 2) {
        std::cout << "{\"success\":false,\"error\":\"Usage: omarchy_ctrl <domain> <action> [args...]\"}" << std::endl;
        return 1;
    }

    std::string domain = argv[1];
    std::string action = (argc >= 3) ? argv[2] : "";
    std::string target = (argc >= 4) ? argv[3] : "";

    bool success = false;
    std::string output = "";

    // 1. HYPRLAND DOMAIN (Direct Sub-Millisecond Lua Socket IPC)
    if (domain == "hypr" || domain == "hyprland") {
        if (action == "close_window" || action == "kill") {
            success = send_hyprland_cmd("dispatch hl.dsp.window.close()", output);
        } else if (action == "close_all" || action == "close_all_windows") {
            success = run_cmd_capture({"omarchy", "hyprland", "window", "close", "all"}, output);
        } else if (action == "fullscreen" || action == "fullscreen_toggle") {
            success = send_hyprland_cmd("dispatch hl.dsp.window.fullscreen({ mode = \"fullscreen\" })", output);
        } else if (action == "fullscreen_tiled" || action == "tiled_fullscreen") {
            success = run_cmd_capture({"omarchy", "hyprland", "window", "tiled", "fullscreen", "toggle"}, output);
        } else if (action == "float" || action == "float_toggle") {
            success = send_hyprland_cmd("dispatch hl.dsp.window.float({ action = \"toggle\" })", output);
        } else if (action == "workspace") {
            std::string ws = target.empty() ? "1" : target;
            success = send_hyprland_cmd("dispatch hl.dsp.focus({ workspace = \"" + ws + "\" })", output);
        } else if (action == "movetoworkspace") {
            std::string ws = target.empty() ? "1" : target;
            success = send_hyprland_cmd("dispatch hl.dsp.window.move({ workspace = \"" + ws + "\" })", output);
        } else if (action == "next_workspace") {
            success = send_hyprland_cmd("dispatch hl.dsp.focus({ workspace = \"e+1\" })", output);
        } else if (action == "prev_workspace") {
            success = send_hyprland_cmd("dispatch hl.dsp.focus({ workspace = \"e-1\" })", output);
        } else if (action == "cyclenext" || action == "next_window") {
            success = send_hyprland_cmd("dispatch hl.dsp.window.cycle_next()", output);
        } else if (action == "cycleprev" || action == "prev_window") {
            success = send_hyprland_cmd("dispatch hl.dsp.window.cycle_next({ next = false })", output);
        } else if (action == "focus") {
            std::string dir = target.empty() ? "r" : target;
            success = send_hyprland_cmd("dispatch hl.dsp.focus({ direction = \"" + dir + "\" })", output);
        } else if (action == "activewindow" || action == "active") {
            success = run_cmd_capture({"hyprctl", "activewindow", "-j"}, output);
        } else if (action == "workspaces") {
            success = run_cmd_capture({"hyprctl", "workspaces", "-j"}, output);
        } else if (action == "clients") {
            success = run_cmd_capture({"hyprctl", "clients", "-j"}, output);
        } else {
            // General hyprland dispatch
            std::string cmd = "dispatch " + action;
            if (!target.empty()) cmd += " " + target;
            success = send_hyprland_cmd(cmd, output);
        }
    }
    // 2. THEME DOMAIN
    else if (domain == "theme") {
        std::vector<std::string> cmd = {"omarchy", "theme"};
        if (action == "next_bg" || action == "next-bg" || action == "bg_next" || action == "next_wallpaper") {
            cmd.push_back("bg");
            cmd.push_back("next");
        } else if (action == "next") {
            cmd.push_back("bg");
            cmd.push_back("next");
        } else if (action == "current") {
            cmd.push_back("current");
        } else if (action == "set") {
            cmd.push_back("set");
            if (!target.empty()) cmd.push_back(target);
        } else if (action == "list") {
            cmd.push_back("list");
        } else if (action == "switcher") {
            cmd.push_back("switcher");
        } else {
            cmd.push_back(action);
            if (!target.empty()) cmd.push_back(target);
        }
        success = run_cmd_capture(cmd, output);
    }
    // 3. TOGGLE DOMAIN
    else if (domain == "toggle") {
        std::vector<std::string> cmd = {"omarchy", "toggle"};
        if (action == "nightlight") {
            cmd.push_back("nightlight");
        } else if (action == "bar") {
            cmd.push_back("bar");
        } else if (action == "touchpad") {
            cmd.push_back("touchpad");
        } else if (action == "screensaver") {
            cmd.push_back("screensaver");
        } else if (action == "stay_awake" || action == "awake") {
            cmd.push_back("idle");
            cmd.push_back("stay-awake");
        } else {
            cmd.push_back(action);
            if (!target.empty()) cmd.push_back(target);
        }
        success = run_cmd_capture(cmd, output);
    }
    // 4. RESTART DOMAIN
    else if (domain == "restart") {
        std::vector<std::string> cmd = {"omarchy", "restart", action};
        success = run_cmd_capture(cmd, output);
    }
    // 5. CAPTURE DOMAIN
    else if (domain == "capture") {
        std::vector<std::string> cmd = {"omarchy", "capture"};
        if (action == "screenshot" || action == "smart") {
            cmd.push_back("screenshot");
            cmd.push_back("smart");
            cmd.push_back("save");
        } else if (action == "fullscreen") {
            cmd.push_back("screenshot");
            cmd.push_back("fullscreen");
            cmd.push_back("save");
        } else if (action == "text" || action == "ocr") {
            cmd.push_back("text");
        } else if (action == "qr") {
            cmd.push_back("qr");
        } else {
            cmd.push_back(action);
            if (!target.empty()) cmd.push_back(target);
        }
        success = run_cmd_capture(cmd, output);
    }
    // 6. LAUNCH DOMAIN
    else if (domain == "launch") {
        std::vector<std::string> cmd = {"omarchy", "launch", action};
        if (!target.empty()) cmd.push_back(target);
        for (int i = 4; i < argc; ++i) {
            cmd.push_back(argv[i]);
        }
        success = run_cmd_capture(cmd, output);
    }
    // 7. SYSTEM DOMAIN
    else if (domain == "system") {
        std::vector<std::string> cmd = {"omarchy", "system", action};
        success = run_cmd_capture(cmd, output);
    }
    // 8. OSD DOMAIN
    else if (domain == "osd") {
        std::vector<std::string> cmd = {"omarchy", "osd", "-m", action};
        if (!target.empty()) {
            cmd.push_back("-i");
            cmd.push_back(target);
        }
        success = run_cmd_capture(cmd, output);
    }
    // 9. RAW ARBITRARY OMARCHY COMMAND
    else if (domain == "raw") {
        std::vector<std::string> cmd = {"omarchy"};
        for (int i = 2; i < argc; ++i) {
            cmd.push_back(argv[i]);
        }
        success = run_cmd_capture(cmd, output);
    }
    else {
        // Treat domain as first argument to omarchy
        std::vector<std::string> cmd = {"omarchy", domain};
        if (!action.empty()) cmd.push_back(action);
        if (!target.empty()) cmd.push_back(target);
        for (int i = 4; i < argc; ++i) {
            cmd.push_back(argv[i]);
        }
        success = run_cmd_capture(cmd, output);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    // Clean trailing newlines
    while (!output.empty() && (output.back() == '\n' || output.back() == '\r')) {
        output.pop_back();
    }

    std::cout << "{"
              << "\"success\":" << (success ? "true" : "false") << ","
              << "\"domain\":\"" << escape_json(domain) << "\","
              << "\"action\":\"" << escape_json(action) << "\","
              << "\"output\":\"" << escape_json(output) << "\","
              << "\"duration_ms\":" << elapsed_ms
              << "}" << std::endl;

    return success ? 0 : 1;
}
